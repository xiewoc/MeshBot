from typing import Optional, Dict, Any, List
import aiohttp
import asyncio
import logging
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AsyncOpenAIChatClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-3.5-turbo",
        organization: Optional[str] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.organization = organization
        self.conversation_history: List[Dict[str, str]] = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logger
        self._lock = asyncio.Lock()

    async def init(self):
        """异步初始化 session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=True),
                timeout=aiohttp.ClientTimeout(total=120),
                headers=self._get_headers(),
            )
            self.logger.info(f"OpenAI客户端已初始化，模型: {self.default_model}")

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        return headers

    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("OpenAI客户端已关闭")

    async def chat(
        self,
        user_name,
        message: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """发送聊天请求"""
        if not message or not message.strip():
            return {"success": False, "error": "消息内容为空", "response": None}

        async with self._lock:
            try:
                await self.init()

                if self.session is None:
                    self.logger.error("aiohttp.ClientSession 未初始化")
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
                    payload["max_tokens"] = max(1, min(4000, max_tokens))

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
                            f"OpenAI API错误: {resp.status} - {error_data}"
                        )
                        return {
                            "success": False,
                            "error": f"API错误: {resp.status} - {error_data}",
                            "response": None,
                        }

            except aiohttp.ClientError as e:
                self.logger.error(f"网络请求失败: {e}")
                return {
                    "success": False,
                    "error": f"网络错误: {str(e)}",
                    "response": None,
                }
            except asyncio.TimeoutError as e:
                self.logger.error(f"请求超时: {e}")
                return {
                    "success": False,
                    "error": f"请求超时: {str(e)}",
                    "response": None,
                }
            except Exception as e:
                self.logger.error(f"聊天处理异常: {e}")
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

        return {
            "success": True,
            "response": ai_response,
            "usage": result.get("usage"),
            "finish_reason": result["choices"][0].get("finish_reason"),
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

        self.logger.debug(f"对话历史更新，当前长度: {len(self.conversation_history)}")

    async def get_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        try:
            await self.init()
            if self.session is None:
                self.logger.error("aiohttp.ClientSession 未初始化")
                raise Exception("aiohttp.ClientSession 未初始化")

            async with self.session.get(f"{self.base_url}/models") as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("data", [])
        except Exception as e:
            self.logger.error(f"获取模型列表失败: {e}")
            return []

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
        self.logger.info("对话历史已清空")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
