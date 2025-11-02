# api/claude_api.py
from typing import Optional, Dict, Any
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)


class AsyncClaudeChatClient:
    def __init__(self, api_key: str, default_model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = "https://api.anthropic.com/v1"
        self.conversation_history = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logger
        self._lock = asyncio.Lock()

    async def init(self):
        """异步初始化 session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120),
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
            )
            self.logger.info(f"Claude客户端已初始化，模型: {self.default_model}")

    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("Claude客户端已关闭")

    async def chat(self, user_name: str, message: str, model: Optional[str] = None,
                  system_prompt: Optional[str] = None, temperature: float = 0.7,
                  max_tokens: int = 1000) -> Dict[str, Any]:
        """发送聊天请求到 Claude API"""
        if not message or not message.strip():
            return {"success": False, "error": "消息内容为空", "response": None}

        async with self._lock:
            try:
                await self.init()
                
                if self.session is None:
                    self.logger.error("aiohttp.ClientSession 未初始化")
                    return {"success": False, "error": "客户端未初始化", "response": None}
                
                model = model or self.default_model
                full_message = f"{user_name}: {message}"
                
                # 构建 Claude 请求格式
                messages = self._build_messages(full_message)
                
                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max(1, min(4096, max_tokens)),
                    "temperature": max(0.0, min(1.0, temperature)),
                }
                
                # 添加系统提示（如果有）
                if system_prompt:
                    payload["system"] = system_prompt

                async with self.session.post(f"{self.base_url}/messages", json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        ai_response = self._extract_response(result)
                        self._update_conversation_history(full_message, ai_response)
                        return {"success": True, "response": ai_response}
                    else:
                        error_text = await resp.text()
                        self.logger.error(f"Claude API错误: {resp.status} - {error_text}")
                        return {"success": False, "error": f"API错误: {resp.status}", "response": None}
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"网络请求失败: {e}")
                return {"success": False, "error": f"网络错误: {str(e)}", "response": None}
            except Exception as e:
                self.logger.error(f"聊天处理异常: {e}")
                return {"success": False, "error": f"处理异常: {str(e)}", "response": None}

    def _build_messages(self, message: str) -> list:
        """构建 Claude 格式的消息列表"""
        messages = []
        
        # 添加对话历史
        for msg in self.conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # 添加当前消息
        messages.append({
            "role": "user",
            "content": message.strip()
        })
        
        return messages

    def _extract_response(self, result: Dict) -> str:
        """从 Claude 响应中提取文本"""
        try:
            if "content" in result and result["content"]:
                for content in result["content"]:
                    if content.get("type") == "text":
                        return content["text"]
            
            self.logger.error(f"无法解析 Claude 响应: {result}")
            return "抱歉，我无法生成回复。"
        except Exception as e:
            self.logger.error(f"解析 Claude 响应失败: {e}")
            return "抱歉，响应解析失败。"

    def _update_conversation_history(self, user_message: str, ai_response: str):
        """更新对话历史"""
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": ai_response})
        
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        self.logger.debug(f"对话历史更新，当前长度: {len(self.conversation_history)}")

    async def get_models(self) -> list:
        """获取可用模型列表"""
        try:
            await self.init()
            if self.session is None:
                self.logger.error("aiohttp.ClientSession 未初始化")
                return []
            
            # Claude API 没有直接的模型列表端点，返回常用模型
            common_models = [
                {"name": "claude-3-opus-20240229", "display_name": "Claude 3 Opus"},
                {"name": "claude-3-sonnet-20240229", "display_name": "Claude 3 Sonnet"},
                {"name": "claude-3-haiku-20240307", "display_name": "Claude 3 Haiku"},
                {"name": "claude-2.1", "display_name": "Claude 2.1"},
                {"name": "claude-2.0", "display_name": "Claude 2.0"},
                {"name": "claude-instant-1.2", "display_name": "Claude Instant 1.2"}
            ]
            return common_models
        except Exception as e:
            self.logger.error(f"获取模型列表异常: {e}")
            return []