# core/bot.py
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import meshtastic
import meshtastic.serial_interface
from pubsub import pub

from meshbot.config.config_loader import _config_manager
from meshbot.utils.ai_client_factory import create_ai_client
from meshbot.core.message_processor import MessageProcessor
from meshbot.utils.localize import i18n

logger = logging.getLogger(__name__)


class MeshBot:
    """Mesh AI 机器人主类，基于 Meshtastic 与 AI 交互"""

    def __init__(self):
        
        self.client = create_ai_client(_config_manager.platform)
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
        logger.info(i18n.gettext('bot_initializing'))
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
                    model_names = [m.get('name', i18n.gettext('unknown')) for m in models]
                    logger.info(
                        i18n.gettext('available_models', model_names=model_names)
                    )
                else:
                    logger.warning(i18n.gettext('no_models_warning'))
        except Exception as e:
            logger.warning(i18n.gettext('model_list_failed', error=e))

    async def _initialize_meshtastic(self) -> None:
        """连接 Meshtastic 设备"""
        try:
            self.interface = meshtastic.serial_interface.SerialInterface()
            self.nodes = self.interface.nodes
            node_info = self.interface.getMyNodeInfo()
            if node_info and 'num' in node_info:
                self._node_id = node_info['num']
                self.message_processor = MessageProcessor(self.nodes, self._node_id)
                logger.info(i18n.gettext('meshtastic_connected', node_id=self._node_id))
            else:
                logger.error(i18n.gettext('node_info_error'))
                raise RuntimeError(i18n.gettext('node_info_error'))
        except Exception as e:
            logger.error(i18n.gettext('meshtastic_connect_failed', error=e))
            raise

    def _register_event_handlers(self) -> None:
        """注册 Meshtastic 消息事件"""
        pub.subscribe(self._on_receive, "meshtastic.receive")
        pub.subscribe(self._on_connection, "meshtastic.connection.established")

    def _on_connection(self, interface, topic=pub.AUTO_TOPIC) -> None:
        """连接建立事件"""
        logger.info(i18n.gettext('connection_established'))

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
            logger.warning(i18n.gettext('event_loop_not_running'))

    async def _queue_message(self, message_data: tuple, interface) -> None:
        """将消息加入异步队列"""
        try:
            await self._message_queue.put((message_data, interface))
            logger.debug(i18n.gettext('message_queued', sender=message_data[0]))
        except Exception as e:
            logger.error(i18n.gettext('queue_failed', error=e))

    async def _process_message_queue(self) -> None:
        """持续处理消息队列"""
        while self.running:
            try:
                message_data, interface = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=_config_manager.message_queue_timeout
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
                logger.error(i18n.gettext('queue_processing_error', error=e))

    async def run(self) -> None:
        """启动机器人主循环"""
        self.running = True
        await self.initialize()
        logger.info(i18n.gettext('bot_started'))

        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info(i18n.gettext('interrupt_received'))
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """安全关闭机器人"""
        if not self.running:
            return
        self.running = False
        logger.info(i18n.gettext('bot_shutting_down'))

        if self.interface:
            self.interface.close()
            logger.info(i18n.gettext('meshtastic_closed'))

        await self.client.close()
        logger.info(i18n.gettext('ai_client_closed'))

        self._executor.shutdown(wait=False)