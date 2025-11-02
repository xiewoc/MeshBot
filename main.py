# main.py v1.0.3
import asyncio
import logging
import os
from pathlib import Path

from meshbot.core.bot import MeshAIBot
from meshbot.handlers.signal_handlers import setup_signal_handlers
from meshbot.config.config_loader import create_example_config

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_config():
    """检查配置文件是否存在，如果不存在则创建示例"""
    config_path = Path(__file__).parent / "config.json"
    if not os.path.exists(config_path):
        logger.warning("⚠️ 未找到 config.json 配置文件")
        logger.info("📝 正在创建示例配置文件...")
        create_example_config()
        logger.info("ℹ️ 请编辑 config.json 文件并重新启动程序")
        return False
    return True


async def main() -> None:
    """主入口"""
    if not check_config():
        return
        
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