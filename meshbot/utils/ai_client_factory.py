# utils/ai_client_factory.py
import importlib
import logging

from meshbot.config.config_loader import get_ai_client_config, get_platform
from meshbot.utils.localize import i18n

logger = logging.getLogger(__name__)


def create_ai_client(platform: str = ""):
    """
    创建指定平台的 AI 客户端，失败时回退到 Ollama。
    如果不指定 platform，则使用配置中的默认平台。
    """
    # 获取配置
    ai_client_config = get_ai_client_config()
    default_platform = get_platform()
    
    # 如果没有指定平台，使用默认平台
    if platform is None:
        platform = default_platform
    
    # 获取配置，优先使用传入的 platform，否则使用默认 PLATFORM
    config = ai_client_config.get(platform) or ai_client_config.get(default_platform)
    if not config:
        logger.error(i18n.gettext('platform_not_found', platform = platform, default_platform = default_platform))
        # 回退到内置 Ollama 配置
        logger.info(i18n.gettext('back_to_ollama'))
        from api.ollama_api import AsyncOllamaChatClient
        return AsyncOllamaChatClient(default_model="qwen2.5:7b")

    try:
        # 动态导入模块和类
        module = importlib.import_module(config["module"])
        client_class = getattr(module, config["class"])

        # 复制 kwargs，避免污染原始配置
        kwargs = config["kwargs"].copy()

        # 创建实例
        logger.info(i18n.gettext('ai_client_created', platform = platform))
        return client_class(**kwargs)

    except (ImportError, AttributeError, KeyError) as e:
        logger.error(
            i18n.gettext('ai_client_creation_failed', platform = platform, error_type = type(e).__name__, error_msg = e)
        )
        try:
            from api.ollama_api import AsyncOllamaChatClient
            return AsyncOllamaChatClient(default_model="qwen2.5:7b")
        except ImportError:
            logger.critical(i18n.gettext('fallback_failed'))
            raise RuntimeError(i18n.gettext('ai_client_init_failed'))