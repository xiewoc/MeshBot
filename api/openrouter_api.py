from typing import Optional, Dict, Any, List
import aiohttp
import asyncio
import logging
import json
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AsyncOpenRouterChatClient:
    """OpenRouter API 客户端，支持从 .env 读取配置"""

    # 默认免费模型（如果 .env 未配置）
    DEFAULT_FREE_MODEL = "google/gemini-2.0-flash-exp:free"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        default_model: Optional[str] = None,
        app_name: str = "MeshBot",
        site_url: Optional[str] = None,
    ):
        """
        初始化 OpenRouter 客户端

        Args:
            api_key: API 密钥，若为 None 则从 .env 的 OPENROUTER_API_KEY 读取
            base_url: API 基础 URL
            default_model: 默认模型，若为 None 则从 .env 的 OPENROUTER_MODEL 读取，
                          如果 .env 也未配置，则使用 DEFAULT_FREE_MODEL
            app_name: 应用名称（用于 HTTP-Referer）
            site_url: 网站 URL（可选，用于 X-Title）
        """
        # 优先使用传入的参数，否则从环境变量读取
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = base_url.rstrip("/")

        # 模型选择优先级：传入参数 > .env 配置 > 默认免费模型
        self.default_model = (
            default_model or os.getenv("OPENROUTER_MODEL") or self.DEFAULT_FREE_MODEL
        )

        self.app_name = app_name
        self.site_url = site_url or os.getenv("OPENROUTER_SITE_URL")

        self.conversation_history: List[Dict[str, str]] = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logger
        self._lock = asyncio.Lock()

        # 验证 API Key
        if not self.api_key:
            self.logger.warning("⚠️ OPENROUTER_API_KEY 未配置，请在 .env 文件中设置")

    async def init(self):
        """异步初始化 session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=True),
                timeout=aiohttp.ClientTimeout(total=120),
                headers=self._get_headers(),
            )
            self.logger.info(
                f"✅ OpenRouter 客户端已初始化，模型: {self.default_model}"
            )

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.app_name,  # OpenRouter 要求
        }

        # 可选：添加网站 URL（用于排行榜展示）
        if self.site_url:
            headers["X-Title"] = self.site_url

        return headers

    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("🔌 OpenRouter 客户端已关闭")

    async def chat(
        self,
        user_name: str,
        message: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        发送聊天请求

        Args:
            user_name: 用户名（会作为消息前缀）
            message: 用户消息内容
            model: 指定模型（可选，默认使用 default_model）
            system_prompt: 系统提示词
            temperature: 温度参数 (0-2)
            max_tokens: 最大生成 token 数
            stream: 是否使用流式响应

        Returns:
            {"success": bool, "response": str, "error": str, ...}
        """
        if not message or not message.strip():
            return {"success": False, "error": "消息内容为空", "response": None}

        async with self._lock:
            try:
                await self.init()

                if self.session is None:
                    self.logger.error("❌ aiohttp.ClientSession 未初始化")
                    return {
                        "success": False,
                        "error": "客户端未初始化",
                        "response": None,
                    }

                model = model or self.default_model
                message = f"{user_name}:{message}"
                messages = self._build_messages(message, system_prompt)

                payload: Dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": max(0.1, min(2.0, temperature)),
                    "stream": stream,
                }

                # 可选参数
                if max_tokens is not None:
                    payload["max_tokens"] = max(1, min(8000, max_tokens))

                async with self.session.post(
                    f"{self.base_url}/chat/completions", json=payload
                ) as resp:
                    if resp.status == 200:
                        if stream:
                            return await self._handle_stream_response(resp)
                        else:
                            return await self._handle_normal_response(resp, message)
                    else:
                        error_data = await self._parse_error_response(resp)
                        self.logger.error(
                            f"❌ OpenRouter API错误: {resp.status} - {error_data}"
                        )
                        return {
                            "success": False,
                            "error": f"API错误: {resp.status} - {error_data}",
                            "response": None,
                        }

            except aiohttp.ClientError as e:
                self.logger.error(f"❌ 网络请求失败: {e}")
                return {
                    "success": False,
                    "error": f"网络错误: {str(e)}",
                    "response": None,
                }
            except asyncio.TimeoutError as e:
                self.logger.error(f"⏱️ 请求超时: {e}")
                return {
                    "success": False,
                    "error": f"请求超时: {str(e)}",
                    "response": None,
                }
            except Exception as e:
                self.logger.error(f"❌ 聊天处理异常: {e}")
                return {
                    "success": False,
                    "error": f"处理异常: {str(e)}",
                    "response": None,
                }

    async def _handle_normal_response(
        self, resp: aiohttp.ClientResponse, user_message: str
    ) -> Dict[str, Any]:
        """处理普通响应"""
        result = await resp.json()
        ai_response = result["choices"][0]["message"]["content"]
        self._update_conversation_history(user_message, ai_response)

        # OpenRouter 特有字段
        openrouter_metadata = {}
        if "id" in result:
            openrouter_metadata["generation_id"] = result["id"]
        if "model" in result:
            openrouter_metadata["model_used"] = result["model"]

        return {
            "success": True,
            "response": ai_response,
            "usage": result.get("usage"),
            "finish_reason": result["choices"][0].get("finish_reason"),
            "metadata": openrouter_metadata,
        }

    async def _handle_stream_response(
        self, resp: aiohttp.ClientResponse
    ) -> Dict[str, Any]:
        """处理流式响应"""
        full_response = ""
        async for line in resp.content:
            line = line.decode("utf-8").strip()
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    if "choices" in chunk and chunk["choices"]:
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            content = delta["content"]
                            full_response += content
                except json.JSONDecodeError:
                    continue

        return {"success": True, "response": full_response, "stream": True}

    async def _parse_error_response(self, resp: aiohttp.ClientResponse) -> str:
        """解析错误响应"""
        try:
            error_data = await resp.json()
            return error_data.get("error", {}).get("message", await resp.text())
        except Exception:
            return await resp.text()

    def _build_messages(
        self, message: str, system_prompt: Optional[str]
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = []

        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加对话历史
        messages.extend(self.conversation_history)

        # 添加当前用户消息
        messages.append({"role": "user", "content": message.strip()})

        return messages

    def _update_conversation_history(self, user_message: str, ai_response: str):
        """更新对话历史"""
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": ai_response})

        # 限制历史记录长度
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        self.logger.debug(
            f"📝 对话历史更新，当前长度: {len(self.conversation_history)}"
        )

    async def get_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        try:
            await self.init()
            if self.session is None:
                self.logger.error("❌ aiohttp.ClientSession 未初始化")
                raise Exception("aiohttp.ClientSession 未初始化")

            async with self.session.get(f"{self.base_url}/models") as resp:
                resp.raise_for_status()
                data = await resp.json()

                # OpenRouter 返回格式：{"data": [...]}
                models = data.get("data", [])

                # 过滤出免费模型
                free_models = [m for m in models if m.get("id", "").endswith(":free")]

                if free_models:
                    self.logger.info(f"📋 找到 {len(free_models)} 个免费模型")
                    return free_models

                return models

        except Exception as e:
            self.logger.error(f"❌ 获取模型列表失败: {e}")
            return []

    async def get_top_free_model(self) -> Optional[str]:
        """获取排名最高的免费模型（按 top-weekly 排序）"""
        try:
            models = await self.get_models()
            free_models = [m for m in models if m.get("id", "").endswith(":free")]

            if free_models:
                # 返回第一个免费模型的 ID
                top_model = free_models[0]["id"]
                self.logger.info(f"🏆 Top 免费模型: {top_model}")
                return top_model
            else:
                self.logger.warning("⚠️ 未找到免费模型，使用默认模型")
                return self.DEFAULT_FREE_MODEL

        except Exception as e:
            self.logger.error(f"❌ 获取 top 免费模型失败: {e}")
            return self.DEFAULT_FREE_MODEL

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
        self.logger.info("🗑️ 对话历史已清空")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
