# core/bot.py
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import meshtastic
import meshtastic.serial_interface
from pubsub import pub

from meshbot.config.config_loader import PLATFORM, MESSAGE_QUEUE_TIMEOUT, load_config
from meshbot.utils.ai_client_factory import create_ai_client
from meshbot.core.message_processor import MessageProcessor

logger = logging.getLogger(__name__)


class MeshAIBot:
    """Mesh AI 机器人主类，基于 Meshtastic 与 AI 交互"""

    def __init__(self):
        # 先加载配置
        load_config()
        
        self.client = create_ai_client(PLATFORM)
        self.interface: Optional[meshtastic.serial_interface.SerialInterface] = None
        self.running = False
        self.nodes = None
        self._node_id: Optional[int] = None
        self._message_queue = asyncio.Queue()
        self._processing_lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self.message_processor: Optional[MessageProcessor] = None

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
                    logger.info(
                        f"✅ 可用 AI 模型: {model_names}"
                    )
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
                self.message_processor = MessageProcessor(self.nodes, self._node_id)
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

    def _on_receive(self, packet: dict, interface) -> None:
        """接收消息事件（同步回调）"""
        if not self.running or packet.get('from') == self._node_id:
            return
        if self.message_processor is not None:
            message_data = self.message_processor.analyze_packet(packet)
            if message_data:
                self._schedule_async_processing(message_data, interface)

    def _schedule_async_processing(self, message_data: tuple, interface) -> None:
        """将消息处理调度到事件循环"""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._queue_message(message_data, interface),
                self._loop
            )
        else:
            logger.warning("⚠️ 事件循环未运行，无法处理消息")

    async def _queue_message(self, message_data: tuple, interface) -> None:
        """将消息加入异步队列"""
        try:
            await self._message_queue.put((message_data, interface))
            logger.debug(f"📩 消息已入队，来自: {message_data[0]}")
        except Exception as e:
            logger.error(f"❌ 消息入队失败: {e}")

    async def _process_message_queue(self) -> None:
        """持续处理消息队列"""
        while self.running:
            try:
                message_data, interface = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=MESSAGE_QUEUE_TIMEOUT
                )
                async with self._processing_lock:
                    if self.message_processor is not None:
                        await self.message_processor.handle_incoming_message(
                            message_data, interface, self.client
                        )
                self._message_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 消息队列处理异常: {e}")

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