import asyncio
import logging
import signal
import importlib
import sys
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, Tuple

import meshtastic
import meshtastic.serial_interface
from pubsub import pub

# =============================
# 配置区
# =============================

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================================
# 从 config.json 加载配置
# ================================
try:
    with open("config.json", "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    raise RuntimeError("配置文件 config.json 未找到，请确保文件存在。")
except json.JSONDecodeError as e:
    raise RuntimeError(f"配置文件格式错误：{e}")

# 解析系统配置
SYSTEM_PROMPT = CONFIG["system"]["system_prompt"]
PLATFORM = CONFIG["system"]["platform"]  # 默认平台（用于回退）
MAX_RESPONSE_LENGTH = CONFIG["system"]["max_response_length"]
MESSAGE_QUEUE_TIMEOUT = CONFIG["system"]["message_queue_timeout"]

# AI 客户端配置
AI_CLIENT_CONFIG = CONFIG["clients"]


# =============================
# 工具函数：创建 AI 客户端（支持回退）
# =============================
def create_ai_client(platform: str):
    """
    创建指定平台的 AI 客户端，失败时回退到 Ollama。
    """
    # 获取配置，优先使用传入的 platform，否则使用默认 PLATFORM
    config = AI_CLIENT_CONFIG.get(platform) or AI_CLIENT_CONFIG.get(PLATFORM)
    if not config:
        logger.error(f"未找到平台 '{platform}' 或默认平台 '{PLATFORM}' 的配置")
        # 回退到内置 Ollama 配置
        logger.info("回退到内置 Ollama 客户端")
        from api.ollama_api import AsyncOllamaChatClient
        return AsyncOllamaChatClient(default_model="qwen2.5:7b")

    try:
        # 动态导入模块和类
        module = importlib.import_module(config["module"])
        client_class = getattr(module, config["class"])

        # 复制 kwargs，避免污染原始配置
        kwargs = config["kwargs"].copy()

        # 创建实例
        return client_class(**kwargs)

    except (ImportError, AttributeError, KeyError) as e:
        logger.error(f"无法创建 AI 客户端 ({platform}): {type(e).__name__} - {e}，回退到 Ollama")
        try:
            from api.ollama_api import AsyncOllamaChatClient
            return AsyncOllamaChatClient(default_model="qwen2.5:7b")
        except ImportError:
            logger.critical("回退失败：无法导入 AsyncOllamaChatClient")
            raise RuntimeError("AI 客户端初始化失败，且无法回退到 Ollama")


# =============================
# 主机器人类
# =============================

class MeshAIBot:
    """Mesh AI 机器人主类，基于 Meshtastic 与 AI 交互"""

    def __init__(self):
        self.client = create_ai_client(PLATFORM)
        self.interface: Optional[meshtastic.serial_interface.SerialInterface] = None
        self.running = False
        self.nodes = None
        self._node_id: Optional[int] = None
        self._message_queue = asyncio.Queue()
        self._processing_lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def initialize(self) -> None:
        """初始化机器人组件"""
        logger.info("正在初始化 Mesh AI 机器人...")
        self._loop = asyncio.get_running_loop()
        await self._initialize_ai_client()
        await self._initialize_meshtastic()
        self._register_event_handlers()
        asyncio.create_task(self._process_message_queue())

    async def _initialize_ai_client(self) -> None:
        """初始化 AI 客户端并列出可用模型"""
        await self.client.init()
        try:
            if hasattr(self.client, "get_models"):
                models = await self.client.get_models()
                if models:
                    model_names = [m.get('name', '未知') for m in models]
                    logger.info(f"✅ 可用 AI 模型: {model_names}")
                else:
                    logger.warning("⚠️ 未找到可用模型，请检查服务")
        except Exception as e:
            logger.warning(f"⚠️ 获取模型列表失败: {e}")

    async def _initialize_meshtastic(self) -> None:
        """连接 Meshtastic 设备"""
        try:
            self.interface = meshtastic.serial_interface.SerialInterface()
            self.nodes = self.interface.nodes
            node_info = self.interface.getMyNodeInfo()
            if node_info and 'num' in node_info:
                self._node_id = node_info['num']
                logger.info(f"✅ Meshtastic 连接成功，节点 ID: {self._node_id}")
            else:
                logger.error("❌ 无法获取 Meshtastic 节点信息")
                raise RuntimeError("无法获取 Meshtastic 节点信息")
        except Exception as e:
            logger.error(f"❌ Meshtastic 连接失败: {e}")
            raise

    def _register_event_handlers(self) -> None:
        """注册 Meshtastic 消息事件"""
        pub.subscribe(self._on_receive, "meshtastic.receive")
        pub.subscribe(self._on_connection, "meshtastic.connection.established")

    def _on_connection(self, interface, topic=pub.AUTO_TOPIC) -> None:
        """连接建立事件"""
        logger.info("🔗 Mesh 设备连接已建立")

    def _on_receive(self, packet: Dict[str, Any], interface) -> None:
        """接收消息事件（同步回调）"""
        if not self.running or packet.get('from') == self._node_id:
            return
        message_data = self._analyze_packet(packet)
        if message_data:
            self._schedule_async_processing(message_data, interface)

    def _schedule_async_processing(self, message_data: Tuple, interface) -> None:
        """将消息处理调度到事件循环"""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._queue_message(message_data, interface),
                self._loop
            )
        else:
            logger.warning("⚠️ 事件循环未运行，无法处理消息")

    async def _queue_message(self, message_data: Tuple, interface) -> None:
        """将消息加入异步队列"""
        try:
            await self._message_queue.put((message_data, interface))
            logger.debug(f"📩 消息已入队，来自: {message_data[0]}")
        except Exception as e:
            logger.error(f"❌ 消息入队失败: {e}")

    def _analyze_packet(self, packet: Dict[str, Any]) -> Optional[Tuple]:
        """解析数据包"""
        if 'decoded' not in packet:
            logger.warning("⚠️ 数据包缺少 'decoded' 字段")
            return None

        from_id = packet.get('from', '未知')
        from_id_hex = packet.get('fromId', '未知')
        to_id = packet.get('to', '未知')
        decoded = packet['decoded']
        message_type = decoded.get('portnum', '未知类型')

        if message_type == 'TEXT_MESSAGE_APP' and to_id == self._node_id:
            return self._process_text_message(packet, from_id, from_id_hex, to_id, decoded)
        elif message_type == 'POSITION_APP':
            self._process_position_message(packet, from_id)
        return None

    def _process_text_message(self, packet: Dict[str, Any], from_id: str, 
                              from_id_hex: str, to_id: str, decoded: Dict[str, Any]) -> Optional[Tuple]:
        """处理文本消息"""
        text = decoded.get('text', '').strip()
        if not text:
            return None

        long_name = self._get_sender_name(from_id_hex)
        self._log_message_reception(from_id, long_name, text, packet)
        return (from_id, to_id, long_name, text)

    def _get_sender_name(self, from_id_hex: str) -> str:
        """获取发送者名称"""
        if not self.nodes:
            return ""
        node_info = self.nodes.get(from_id_hex)
        if isinstance(node_info, dict):
            long_name = node_info.get('user', {}).get('longName', '')
            if long_name:
                logger.info(f"👤 节点 {from_id_hex} 名称: {long_name}")
            return long_name
        else:
            logger.warning(f"⚠️ 节点 {from_id_hex} 信息非字典类型")
            return ""

    def _log_message_reception(self, from_id: str, long_name: str, text: str, packet: Dict[str, Any]) -> None:
        """记录消息日志"""
        rssi = packet.get('rxRssi')
        snr = packet.get('rxSnr')
        name_info = f"({long_name})" if long_name else ""
        logger.info(f"📩 收到来自 {from_id}{name_info} 的消息: {text[:50]}{'...' if len(text) > 50 else ''}")
        if rssi is not None:
            logger.debug(f"📶 RSSI: {rssi} dBm")
        if snr is not None:
            logger.debug(f"🔊 SNR: {snr} dB")

    def _process_position_message(self, packet: Dict[str, Any], from_id: str) -> None:
        """处理位置消息"""
        location_info = self._parse_from_and_position(packet)
        if location_info:
            pos = location_info['position']
            if pos:
                logger.info(f"📍 收到 {from_id} 的位置: {pos['latitude']:.6f}, {pos['longitude']:.6f}")

    def _parse_from_and_position(self, packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析位置数据包"""
        result = {}
        from_id_int = packet.get('from')
        if not from_id_int:
            logger.error("❌ 缺少 'from' 字段")
            return None

        node_hex = f"{from_id_int:08x}".lower()
        result['node_id'] = {
            'decimal': from_id_int,
            'hex': node_hex,
            'formatted': f"!{node_hex}"
        }

        decoded = packet.get('decoded')
        if not decoded or decoded.get('portnum') != 'POSITION_APP':
            result['position'] = None
        else:
            result['position'] = self._extract_position_data(decoded.get('position'))

        return result

    def _extract_position_data(self, position: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """提取位置字段"""
        if not position:
            logger.warning("⚠️ 位置数据为空")
            return None

        lat = position.get('latitude')
        lon = position.get('longitude')
        alt = position.get('altitude')

        if lat is None or lon is None:
            logger.error("❌ 缺失经纬度")
            return None

        logger.info(f"🌍 位置: {lat:.6f}°N, {lon:.6f}°E, 海拔: {alt or 'N/A'}m")
        return {'latitude': lat, 'longitude': lon, 'altitude': alt}

    async def _process_message_queue(self) -> None:
        """持续处理消息队列"""
        while self.running:
            try:
                message_data, interface = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=MESSAGE_QUEUE_TIMEOUT
                )
                async with self._processing_lock:
                    await self._handle_incoming_message(message_data, interface)
                self._message_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 消息队列处理异常: {e}")

    async def _handle_incoming_message(self, message_data: Tuple, interface) -> None:
        """调用 AI 并回复消息"""
        from_id, to_id, long_name, text = message_data
        try:
            result = await self.client.chat(long_name, text, system_prompt=SYSTEM_PROMPT)
            if result["success"]:
                response = result['response'][:MAX_RESPONSE_LENGTH]
                logger.info(f"🤖 AI 回复: {response}")
                if isinstance(response, (str, list, tuple)) and len(response) > 200:
                    response = response[:200]
                interface.sendText(response, from_id)
            else:
                error_msg = result.get('error', '未知错误')
                logger.error(f"❌ AI 处理失败: {error_msg}")
                interface.sendText(f"❌ 处理失败: {error_msg}", from_id)
        except Exception as e:
            logger.error(f"❌ 消息处理异常: {e}")
            interface.sendText("❌ 处理异常，请稍后重试", from_id)

    async def run(self) -> None:
        """启动机器人主循环"""
        self.running = True
        await self.initialize()
        logger.info("🚀 Mesh AI 机器人已启动，按 Ctrl+C 退出...")

        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 收到中断信号，正在关闭...")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """安全关闭机器人"""
        if not self.running:
            return
        self.running = False
        logger.info("🔧 正在关闭 Mesh AI 机器人...")

        if self.interface:
            self.interface.close()
            logger.info("🔌 Meshtastic 连接已关闭")

        await self.client.close()
        logger.info("🧠 AI 客户端已关闭")

        self._executor.shutdown(wait=False)


# =============================
# 信号处理
# =============================

def setup_signal_handlers(bot: MeshAIBot) -> None:
    """注册信号处理器以优雅关闭"""
    def signal_handler(sig, frame):
        logger.info(f"🛑 收到信号 {sig}，正在关闭...")
        if bot._loop and bot._loop.is_running():
            asyncio.run_coroutine_threadsafe(bot.shutdown(), bot._loop)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


# =============================
# 主函数
# =============================

async def main() -> None:
    """主入口"""
    bot = MeshAIBot()
    setup_signal_handlers(bot)
    try:
        await bot.run()
    except Exception as e:
        logger.error(f"💥 机器人运行异常: {e}")
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())