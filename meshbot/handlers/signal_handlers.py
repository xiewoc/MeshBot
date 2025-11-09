# handlers/signal_handlers.py
import signal
import sys
import asyncio
import logging
from meshbot.utils.localize import i18n

logger = logging.getLogger(__name__)


def setup_signal_handlers(bot) -> None:
    """注册信号处理器以优雅关闭"""
    def signal_handler(sig, frame):
        logger.info(i18n.gettext('recieced_sig_closing',sig = sig))
        if bot._loop and bot._loop.is_running():
            asyncio.run_coroutine_threadsafe(bot.shutdown(), bot._loop)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)