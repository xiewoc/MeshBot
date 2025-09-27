import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import asyncio
import logging
import aiohttp
import signal
import sys
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

system_prompt = "你是一个有用的助手，请用简洁的语言回复。"

class AsyncOllamaChatClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", default_model: str = "qwen2.5:7b"):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.conversation_history = []
        self.session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()

    async def init(self):
        """异步初始化 session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=120)
            )
            logger.info(f"Ollama客户端已初始化，模型: {self.default_model}")

    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Ollama客户端已关闭")

    async def chat(self, message: str, model: Optional[str] = None, 
                  system_prompt: Optional[str] = None, temperature: float = 0.7, 
                  max_tokens: int = 1000) -> Dict[str, Any]:
        """发送聊天请求"""
        if not message or not message.strip():
            return {"success": False, "error": "消息内容为空", "response": None}

        async with self._lock:
            try:
                await self.init()
                
                model = model or self.default_model
                messages = self._build_messages(message, system_prompt)
                
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": max(0.1, min(1.0, temperature)),
                        "num_predict": max(10, min(4000, max_tokens)),
                        "num_ctx": 4096
                    }
                }

                async with self.session.post(f"{self.base_url}/api/chat", json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        ai_response = result["message"]["content"]
                        self._update_conversation_history(message, ai_response)
                        return {"success": True, "response": ai_response}
                    else:
                        error_text = await resp.text()
                        logger.error(f"Ollama API错误: {resp.status} - {error_text}")
                        return {"success": False, "error": f"API错误: {resp.status}", "response": None}
                        
            except aiohttp.ClientError as e:
                logger.error(f"网络请求失败: {e}")
                return {"success": False, "error": f"网络错误: {str(e)}", "response": None}
            except Exception as e:
                logger.error(f"聊天处理异常: {e}")
                return {"success": False, "error": f"处理异常: {str(e)}", "response": None}

    def _build_messages(self, message: str, system_prompt: Optional[str]) -> list:
        """构建消息列表"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": message.strip()})
        return messages

    def _update_conversation_history(self, user_message: str, ai_response: str):
        """更新对话历史"""
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": ai_response})
        
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        logger.debug(f"对话历史更新，当前长度: {len(self.conversation_history)}")

    async def get_models(self) -> list:
        """获取可用模型列表"""
        try:
            await self.init()
            async with self.session.get(f"{self.base_url}/api/tags") as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("models", [])
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []

class MeshAIBot:
    def __init__(self):
        self.client = AsyncOllamaChatClient()
        self.interface: Optional[meshtastic.serial_interface.SerialInterface] = None
        self.running = False
        self._message_queue = asyncio.Queue()
        self._processing_lock = asyncio.Lock()
        self._loop = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def initialize(self):
        """初始化机器人"""
        logger.info("正在初始化Mesh AI机器人...")
        
        # 保存事件循环引用
        self._loop = asyncio.get_running_loop()
        
        # 初始化Ollama客户端
        await self.client.init()
        
        # 检查可用模型
        models = await self.client.get_models()
        if models:
            logger.info(f"可用模型: {[m['name'] for m in models]}")
        else:
            logger.warning("未找到可用模型，请检查Ollama服务")
        
        # 连接Meshtastic设备
        try:
            self.interface = meshtastic.serial_interface.SerialInterface()
            logger.info("Meshtastic设备连接成功")
        except Exception as e:
            logger.error(f"Meshtastic设备连接失败: {e}")
            raise
        
        # 注册事件处理器
        pub.subscribe(self._on_receive, "meshtastic.receive")
        pub.subscribe(self._on_connection, "meshtastic.connection.established")
        
        # 启动消息处理任务
        asyncio.create_task(self._process_message_queue())

    def _on_connection(self, interface, topic=pub.AUTO_TOPIC):
        """设备连接事件处理"""
        logger.info("Mesh设备连接已建立")

    def _on_receive(self, packet, interface):
        """消息接收事件处理（同步函数）"""
        if not self.running:
            return
            
        # 防止处理自己的消息
        if packet.get('from') == interface.getMyNodeInfo()['num']:
            return
            
        # 解析数据包
        message_data = self._analyze_packet(packet)
        if message_data:
            # 使用线程安全的方式提交异步任务
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._queue_message(message_data, interface), 
                    self._loop
                )
            else:
                logger.warning("事件循环未运行，无法处理消息")

    async def _queue_message(self, message_data, interface):
        """将消息加入处理队列"""
        try:
            await self._message_queue.put((message_data, interface))
            logger.debug(f"消息已加入队列，来自节点: {message_data[0]}")
        except Exception as e:
            logger.error(f"消息入队失败: {e}")

    def _parse_from_and_position(self, packet):
        """
        解析 packet 中的 'from' 节点信息和位置数据
        """
        result = {}

        # === 1. 解析 'from' 节点 ID ===
        from_id_int = packet.get('from')
        from_id_str = packet.get('fromId', None)

        if from_id_int is None:
            print("❌ 缺少 'from' 字段")
            return None

        # 转换为十六进制（8位，小写）
        node_hex = f"{from_id_int:08x}".lower()
        node_id_formatted = f"!{node_hex}"

        print(f"📡 来源节点 (Node ID):")
        print(f"   十进制: {from_id_int}")
        print(f"   十六进制: {node_hex}")
        print(f"   格式化: {node_id_formatted}")

        result['node_id'] = {
            'decimal': from_id_int,
            'hex': node_hex,
            'formatted': node_id_formatted
        }

        # === 2. 解析位置信息（如果存在）===
        decoded = packet.get('decoded')
        if not decoded:
            print("⚠️  警告: 数据包未解码，无位置信息")
            result['position'] = None
        elif decoded.get('portnum') != 'POSITION_APP':
            print("⚠️  警告: 此包不是位置消息")
            result['position'] = None
        else:
            pos = decoded.get('position')
            if not pos:
                print("⚠️  警告: 位置字段为空")
                result['position'] = None
            else:
                lat = pos.get('latitude')
                lon = pos.get('longitude')
                alt = pos.get('altitude')

                if lat is None or lon is None:
                    print("❌ 缺少经纬度")
                    result['position'] = None
                else:
                    print(f"🌍 位置信息:")
                    print(f"   纬度 (Latitude):  {lat:.7f}°")
                    print(f"   经度 (Longitude): {lon:.7f}°")
                    print(f"   海拔 (Altitude):  {alt or 'N/A'} m")

                    result['position'] = {
                        'latitude': lat,
                        'longitude': lon,
                        'altitude': alt
                    }

        return result
    async def _process_message_queue(self):
        """处理消息队列"""
        while self.running:
            try:
                message_data, interface = await self._message_queue.get()
                async with self._processing_lock:
                    await self._handle_incoming_message(message_data, interface)
                self._message_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"消息处理异常: {e}")

    def _analyze_packet(self, packet) -> Optional[tuple]:
        """分析数据包"""
        if 'decoded' not in packet:
            logger.warning("数据包格式错误：缺少decoded字段")
            return None

        from_id = packet.get('from', '未知')
        to_id = packet.get('to', '未知')
        decoded = packet['decoded']
        message_type = decoded.get('portnum', '未知类型')
        
        if message_type == 'TEXT_MESSAGE_APP':
            text = decoded.get('text', '').strip()
            if not text:
                return None
                
            rssi = packet.get('rxRssi')
            snr = packet.get('rxSnr')
            
            logger.info(f"收到来自 {from_id} 的消息: {text[:50]}{'...' if len(text) > 50 else ''}")
            if rssi is not None:
                logger.debug(f"信号强度: {rssi} dBm")
            if snr is not None:
                logger.debug(f"信噪比: {snr} dB")
                
            return (from_id, to_id, text)
        
        elif message_type == 'POSITION_APP':
            loc = self._parse_from_and_position(packet)
            logger.info(f"收到来自 {from_id} 的位置信息: {loc}")
            return None
            
        return None

    async def _handle_incoming_message(self, message_data, interface):
        """处理接收到的消息"""
        from_id, to_id, text = message_data
        
        try:
            # 调用AI生成回复
            result = await self.client.chat(text, system_prompt=system_prompt)
            
            if result["success"]:
                response = result['response'][:200]  # 限制回复长度
                logger.info(f"AI回复: {response}")
                
                # 发送回复
                interface.sendText(response, from_id)
                logger.info(f"回复已发送到节点 {from_id}")
            else:
                error_msg = result.get('error', '未知错误')
                logger.error(f"AI处理失败: {error_msg}")
                interface.sendText(f"处理失败: {error_msg}", from_id)
                
        except Exception as e:
            logger.error(f"消息处理异常: {e}")
            interface.sendText("处理异常，请稍后重试", from_id)

    async def run(self):
        """运行机器人"""
        self.running = True
        await self.initialize()
        
        logger.info("Mesh AI机器人已启动，按Ctrl+C退出...")
        
        try:
            # 主循环
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """关闭机器人"""
        self.running = False
        logger.info("正在关闭Mesh AI机器人...")
        
        if self.interface:
            self.interface.close()
            logger.info("Meshtastic连接已关闭")
        
        await self.client.close()
        logger.info("Ollama客户端已关闭")
        
        self._executor.shutdown(wait=False)

# 全局信号处理
def setup_signal_handlers(bot: MeshAIBot):
    def signal_handler(sig, frame):
        logger.info("收到关闭信号")
        # 使用线程执行异步关闭
        if bot._loop and bot._loop.is_running():
            asyncio.run_coroutine_threadsafe(bot.shutdown(), bot._loop)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """主函数"""
    bot = MeshAIBot()
    
    try:
        await bot.run()
    except Exception as e:
        logger.error(f"机器人运行异常: {e}")
    finally:
        await bot.shutdown()

if __name__ == "__main__":
    asyncio.run(main())