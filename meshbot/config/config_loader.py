# config/config_loader.py
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional 
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Pydantic 模型定义
class ClientConfig(BaseModel):
    """客户端配置模型"""
    module: str
    class_name: str = Field(alias="class")  # 解决 'class' 关键字冲突
    kwargs: Dict[str, Any] = Field(default_factory=dict)

    def __getitem__(self, item):
        if item == "class":
            return getattr(self, "class_name")
        return getattr(self, item)

class SystemConfig(BaseModel):
    """系统配置模型"""
    system_prompt: str = "你是一个助手,请用简洁的语言(小于200字符)回复。"
    max_response_length: int = 200
    message_queue_timeout: int = 1

class LocalizationConfig(BaseModel):
    """本地化配置模型"""
    language: str = "zh_CN"
    timezone: str = "Asia/Shanghai"
    encoding: str = "utf-8"

class AppConfig(BaseModel):
    """应用配置模型"""
    platform: str = "ollama"
    api_keys: Dict[str, str] = Field(default_factory=dict)
    model_settings: Dict[str, str] = Field(default_factory=dict)
    service_urls: Dict[str, str] = Field(default_factory=dict)
    system_prompt: Optional[str] = None

class FullConfig(BaseModel):
    """完整配置模型"""
    system: SystemConfig = Field(default_factory=SystemConfig)
    localization: LocalizationConfig = Field(default_factory=LocalizationConfig)
    clients: Dict[str, ClientConfig] = Field(default_factory=dict)
    app: AppConfig = Field(default_factory=AppConfig)

class ConfigManager:
    """配置管理器（使用 Pydantic 验证）"""
    
    # 默认配置
    DEFAULT_CONFIG: Dict[str, Any] = {
        "system": {
            "system_prompt": "你是一个助手,请用简洁的语言(小于200字符)回复。",
            "max_response_length": 200,
            "message_queue_timeout": 1
        },
        "localization": {
            "language": "zh_CN",
            "timezone": "Asia/Shanghai", 
            "encoding": "utf-8"
        },
        "clients": {
            "ollama": {
                "module": "meshbot.api.ollama_api",
                "class": "AsyncOllamaChatClient",
                "kwargs": {
                    "default_model": "qwen2.5:7b"
                }
            },
            "openai": {
                "module": "meshbot.api.openai_api", 
                "class": "AsyncOpenAIChatClient",
                "kwargs": {
                    "api_key": "your-api-key",
                    "default_model": "gpt-3.5-turbo"
                }
            },
            "deepseek": {
                "module": "meshbot.api.deepseek_api",
                "class": "AsyncDeepSeekChatClient", 
                "kwargs": {
                    "api_key": "your-api-key",
                    "default_model": "deepseek-chat"
                }
            },
            "openrouter": {
                "module": "meshbot.api.openrouter_api",
                "class": "AsyncOpenRouterChatClient",
                "kwargs": {
                    "app_name": "MeshBot",
                    "api_key": "your-api-key"
                }
            },
            "gemini": {
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
                    "uri": "ws://localhost:9238"
                }
            },
            "fastapi": {
                "module": "meshbot.api.fastapi_client",
                "class": "AsyncFastAPIChatClient",
                "kwargs": {
                    "base_url": "http://127.0.0.1:8000",
                    "api_key": "your-fastapi-token"
                }
            }
        }
    }
    
    _instance: Optional['ConfigManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self._config: Optional[FullConfig] = None
        self._user_config: Optional[Dict[str, Any]] = None
        self._config_path: Optional[Path] = None
    
    def load(self, config_path: Optional[str] = None) -> None:
        """从 JSON 文件加载配置并与默认配置合并"""
        if config_path is None:
            config_path = self.get_default_config_path()
        
        self._config_path = Path(config_path)
        
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._user_config = json.load(f)
        except FileNotFoundError:
            raise RuntimeError(f"配置文件未找到: {config_path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"配置文件格式错误: {e}")
        except Exception as e:
            raise RuntimeError(f"读取配置文件失败: {e}")
        
        # 合并配置
        merged_config = self._deep_merge(self.DEFAULT_CONFIG.copy(), self._user_config or {})
        
        # 使用 Pydantic 验证和转换
        try:
            self._config = FullConfig(**merged_config)
        except Exception as e:
            raise RuntimeError(f"配置验证失败: {e}")
        
        # 应用用户配置覆盖
        self._apply_user_overrides()
        
        logger.info("✅ 配置加载成功")
        logger.info(f"🎯 当前平台: {self.platform}")
        logger.info(f"🌐 语言设置: {self.language}")
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并两个字典"""
        for key, value in update.items():
            if (key in base and 
                isinstance(base[key], dict) and 
                isinstance(value, dict)):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
    
    def _apply_user_overrides(self) -> None:
        """应用用户特定的配置覆盖"""
        if not self._user_config or not self._config:
            return
        
        # 应用 API keys
        if "api_keys" in self._user_config:
            for platform, api_key in self._user_config["api_keys"].items():
                if (platform in self._config.clients and 
                    api_key not in ["your-api-key", "your-openai-api-key", ""]):
                    if self._config.clients[platform].kwargs.get("api_key", "").startswith("your-"):
                        self._config.clients[platform].kwargs["api_key"] = api_key
        
        # 应用模型设置
        if "model_settings" in self._user_config:
            for platform, model in self._user_config["model_settings"].items():
                if platform in self._config.clients:
                    if "default_model" in self._config.clients[platform].kwargs:
                        self._config.clients[platform].kwargs["default_model"] = model
        
        # 应用服务 URLs
        if "service_urls" in self._user_config:
            ws_url = self._user_config["service_urls"].get("websockets")
            if ws_url and ws_url != "ws://localhost:9238" and "websockets" in self._config.clients:
                self._config.clients["websockets"].kwargs["uri"] = ws_url
                
            fastapi_url = self._user_config["service_urls"].get("fastapi") 
            if fastapi_url and fastapi_url != "http://127.0.0.1:8000" and "fastapi" in self._config.clients:
                self._config.clients["fastapi"].kwargs["base_url"] = fastapi_url
        
        # 应用系统提示
        if "system_prompt" in self._user_config and self._user_config["system_prompt"]:
            self._config.system.system_prompt = self._user_config["system_prompt"]
    
    def get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        return str((Path(__file__).parent / "../../config.json").resolve())
    
    @property
    def platform(self) -> str:
        """获取当前平台"""
        if self._user_config is None:
            raise RuntimeError("配置未加载")
        return self._user_config.get("platform", "ollama")
    
    @property
    def system_prompt(self) -> str:
        """获取系统提示"""
        if self._config is None:
            raise RuntimeError("配置未加载")
        return self._config.system.system_prompt
    
    @property
    def max_response_length(self) -> int:
        """获取最大响应长度"""
        if self._config is None:
            raise RuntimeError("配置未加载")
        return self._config.system.max_response_length
    
    @property
    def message_queue_timeout(self) -> int:
        """获取消息队列超时时间"""
        if self._config is None:
            raise RuntimeError("配置未加载")
        return self._config.system.message_queue_timeout
    
    @property
    def ai_client_config(self) -> Dict[str, ClientConfig]:
        """获取 AI 客户端配置"""
        if self._config is None:
            raise RuntimeError("配置未加载")
        return self._config.clients
    
    @property 
    def language(self) -> str:
        """获取语言设置"""
        if self._config is None:
            raise RuntimeError("配置未加载")
        return self._config.localization.language
    
    @property
    def timezone(self) -> str:
        """获取时区设置"""
        if self._config is None:
            raise RuntimeError("配置未加载")
        return self._config.localization.timezone
    
    @property
    def encoding(self) -> str:
        """获取编码设置"""
        if self._config is None:
            raise RuntimeError("配置未加载")
        return self._config.localization.encoding
    
    def get_client_config(self, client_name: str) -> Optional[ClientConfig]:
        """获取特定客户端的配置"""
        clients = self.ai_client_config
        return clients.get(client_name)
    
    def reload(self, config_path: Optional[str] = None) -> None:
        """重新加载配置"""
        self._config = None
        self._user_config = None
        self.load(config_path)
        logger.info("🔄 配置重新加载成功")
    
    def create_example_config(self, overwrite: bool = False) -> str:
        """创建示例配置文件
        
        Args:
            overwrite: 是否覆盖已存在的文件
            
        Returns:
            配置文件路径
        """
        config_path = Path(self.get_default_config_path())
        
        if config_path.exists() and not overwrite:
            raise FileExistsError(f"配置文件已存在: {config_path}")
        
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
            },
            "system_prompt": "你是一个助手,请用简洁的语言(小于200字符)回复。",
            "localization": {
                "language": "zh_CN",
                "timezone": "Asia/Shanghai",
                "encoding": "utf-8"
            }
        }
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(example_config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📝 示例配置文件已创建: {config_path}")
        return str(config_path)
    
    def get_current_config(self) -> FullConfig:
        """获取当前配置（用于调试）"""
        if self._config is None:
            raise RuntimeError("配置未加载")
        return self._config


# 全局单例实例
_config_manager = ConfigManager()

# 兼容旧接口的快捷函数
def load_config(config_path: Optional[str] = None) -> None:
    """加载配置（兼容旧接口）"""
    _config_manager.load(config_path)

def get_platform() -> str:
    """获取平台配置（兼容旧接口）"""
    return _config_manager.platform

def get_system_prompt() -> str:
    """获取系统提示（兼容旧接口）"""
    return _config_manager.system_prompt

def get_max_response_length() -> int:
    """获取最大响应长度（兼容旧接口）"""
    return _config_manager.max_response_length

def get_message_queue_timeout() -> int:
    """获取消息队列超时时间（兼容旧接口）"""
    return _config_manager.message_queue_timeout

def get_ai_client_config() -> Dict[str, ClientConfig]:
    """获取 AI 客户端配置（兼容旧接口）"""
    return _config_manager.ai_client_config

def get_localization_config() -> LocalizationConfig:
    """获取本地化配置"""
    if _config_manager._config is None:
        raise RuntimeError("配置未加载")
    return _config_manager._config.localization

def create_example_config(overwrite: bool = False) -> str:
    """创建示例配置文件（兼容旧接口）"""
    return _config_manager.create_example_config(overwrite)

def reload_config(config_path: Optional[str] = None) -> None:
    """重新加载配置（兼容旧接口）"""
    _config_manager.reload(config_path)