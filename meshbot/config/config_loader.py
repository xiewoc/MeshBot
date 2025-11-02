# config/config_loader.py
import json
import logging
from pathlib import Path  

logger = logging.getLogger(__name__)

# 默认配置（不常修改的部分）
DEFAULT_CONFIG = {
    "system": {
        "system_prompt": "你是一个助手,请用简洁的语言(小于200字符)回复。",
        "max_response_length": 200,
        "message_queue_timeout": 1
    },
    "clients": {
        "ollama": {
            "module": "meshbot.api.ollama_api",
            "class": "AsyncOllamaChatClient",
            "kwargs": {
                "default_model": "qwen2.5:7b"  # 会被用户配置覆盖
            }
        },
        "openai": {
            "module": "meshbot.api.openai_api",
            "class": "AsyncOpenAIChatClient",
            "kwargs": {
                "api_key": "your-api-key",  # 会被用户配置覆盖
                "default_model": "gpt-3.5-turbo"  # 会被用户配置覆盖
            }
        },
        "deepseek": {
            "module": "meshbot.api.deepseek_api",
            "class": "AsyncDeepSeekChatClient",
            "kwargs": {
                "api_key": "your-api-key",  # 会被用户配置覆盖
                "default_model": "deepseek-chat"  # 会被用户配置覆盖
            }
        },
        "openrouter": {
            "module": "meshbot.api.openrouter_api",
            "class": "AsyncOpenRouterChatClient",
            "kwargs": {
                "app_name": "MeshBot",
                "api_key": "your-api-key"  # 会被用户配置覆盖
            }
        },"gemini": {
            "module": "meshbot.api.gemini_api",
            "class": "AsyncGeminiChatClient",
            "kwargs": {
                "api_key": "your-gemini-api-key",
                "default_model": "gemini-pro"
            }
        },
        "claude": {
            "module": "meshbot.api.claude_api",
            "class": "AsyncClaudeChatClient",
            "kwargs": {
                "api_key": "your-claude-api-key",
                "default_model": "claude-3-sonnet-20240229"
            }
        },
        "siliconflow": {
            "module": "meshbot.api.siliconflow_api",
            "class": "AsyncSiliconFlowChatClient",
            "kwargs": {
                "api_key": "your-siliconflow-api-key",
                "default_model": "deepseek-ai/DeepSeek-V2-Chat"
            }
        },
        "websockets": {
            "module": "meshbot.api.ws_platform",
            "class": "AsyncWebSocketsClient",
            "kwargs": {
                "uri": "ws://localhost:9238"  # 会被用户配置覆盖
            }
        },
        "fastapi": {
            "module": "meshbot.api.fastapi_client",
            "class": "AsyncFastAPIChatClient", 
            "kwargs": {
                "base_url": "http://127.0.0.1:8000",
                "api_key": "your-fastapi-token"  # 可选
            }
        },
    }
}

# 合并后的配置
CONFIG = None
SYSTEM_PROMPT = None
PLATFORM = None
MAX_RESPONSE_LENGTH = None
MESSAGE_QUEUE_TIMEOUT = None
AI_CLIENT_CONFIG = None


def load_config(config_path: str = str((Path(__file__).parent / "../../config.json").resolve())) -> None:
    """从 JSON 文件加载配置并与默认配置合并"""
    global CONFIG, SYSTEM_PROMPT, PLATFORM, MAX_RESPONSE_LENGTH, MESSAGE_QUEUE_TIMEOUT, AI_CLIENT_CONFIG
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
    except FileNotFoundError:
        raise RuntimeError("配置文件 config.json 未找到，请确保文件存在。")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"配置文件格式错误：{e}")

    # 合并配置
    CONFIG = _merge_configs(DEFAULT_CONFIG, user_config)
    
    # 解析系统配置
    SYSTEM_PROMPT = CONFIG["system"]["system_prompt"]
    PLATFORM = user_config.get("platform", "ollama")  # 从用户配置获取平台
    MAX_RESPONSE_LENGTH = CONFIG["system"]["max_response_length"]
    MESSAGE_QUEUE_TIMEOUT = CONFIG["system"]["message_queue_timeout"]

    # AI 客户端配置
    AI_CLIENT_CONFIG = CONFIG["clients"]
    
    logger.info("✅ 配置加载成功")
    logger.info(f"🎯 当前平台: {PLATFORM}")


def _merge_configs(default_config: dict, user_config: dict) -> dict:
    """深度合并默认配置和用户配置"""
    result = default_config.copy()
    
    # 处理 API keys
    if "api_keys" in user_config:
        for platform, api_key in user_config["api_keys"].items():
            if platform in result["clients"] and api_key != "your-api-key":
                if "kwargs" in result["clients"][platform]:
                    result["clients"][platform]["kwargs"]["api_key"] = api_key
    
    # 处理模型设置
    if "model_settings" in user_config:
        for platform, model in user_config["model_settings"].items():
            if platform in result["clients"]:
                if "kwargs" in result["clients"][platform]:
                    result["clients"][platform]["kwargs"]["default_model"] = model
    
    # 处理服务 URLs
    if "service_urls" in user_config:
        # WebSocket
        ws_url = user_config["service_urls"].get("websockets")
        if ws_url and ws_url != "ws://localhost:9238" and "websockets" in result["clients"]:
            result["clients"]["websockets"]["kwargs"]["uri"] = ws_url
            
        # FastAPI
        fastapi_url = user_config["service_urls"].get("fastapi") 
        if fastapi_url and fastapi_url != "http://127.0.0.1:8000" and "fastapi" in result["clients"]:
            result["clients"]["fastapi"]["kwargs"]["base_url"] = fastapi_url
      
    # 处理系统提示（可选，如果用户想要自定义）
    if "system_prompt" in user_config:
        result["system"]["system_prompt"] = user_config["system_prompt"]
    
    return result


def get_ai_client_config():
    """获取 AI 客户端配置"""
    if AI_CLIENT_CONFIG is None:
        raise RuntimeError("配置未加载，请先调用 load_config()")
    return AI_CLIENT_CONFIG


def get_platform():
    """获取平台配置"""
    if PLATFORM is None:
        raise RuntimeError("配置未加载，请先调用 load_config()")
    return PLATFORM


def get_system_prompt():
    """获取系统提示"""
    if SYSTEM_PROMPT is None:
        raise RuntimeError("配置未加载，请先调用 load_config()")
    return SYSTEM_PROMPT


def get_max_response_length():
    """获取最大响应长度"""
    if MAX_RESPONSE_LENGTH is None:
        raise RuntimeError("配置未加载，请先调用 load_config()")
    return MAX_RESPONSE_LENGTH


def get_message_queue_timeout():
    """获取消息队列超时时间"""
    if MESSAGE_QUEUE_TIMEOUT is None:
        raise RuntimeError("配置未加载，请先调用 load_config()")
    return MESSAGE_QUEUE_TIMEOUT


def create_example_config():
    """创建示例配置文件"""
    example_config = {
        "platform": "ollama",
        "api_keys": {
            "openai": "your-openai-api-key",
            "deepseek": "your-deepseek-api-key",
            "openrouter": "your-openrouter-api-key",
            "gemini": "your-gemini-api-key",
            "claude": "your-claude-api-key",
            "siliconflow": "your-siliconflow-api-key",
            "fastapi": "your-fastapi-token"
        },
        "model_settings": {
            "ollama": "qwen2.5:7b",
            "openai": "gpt-3.5-turbo",
            "deepseek": "deepseek-chat",
            "openrouter": "openai/gpt-3.5-turbo",
            "gemini": "gemini-pro",
            "claude": "claude-3-sonnet-20240229",
            "siliconflow": "deepseek-ai/DeepSeek-V2-Chat",
            "fastapi": "fastapi-default"
        },
        "service_urls": {
            "websockets": "ws://localhost:9238",
            "fastapi": "http://127.0.0.1:8000"
        }
    }
    
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(example_config, f, indent=2, ensure_ascii=False)
    
    logger.info("📝 示例配置文件 config.json 已创建")