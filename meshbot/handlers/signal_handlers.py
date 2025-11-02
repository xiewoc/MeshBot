# handlers/signal_handlers.py
import signal
import sys
import asyncio
import logging

logger = logging.getLogger(__name__)


def setup_signal_handlers(bot) -> None:
    """注册信号处理器以优雅关闭"""
    def signal_handler(sig, frame):
        logger.info(f"🛑 收到信号 {sig}，正在关闭...")
        if bot._loop and bot._loop.is_running():
            asyncio.run_coroutine_threadsafe(bot.shutdown(), bot._loop)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)