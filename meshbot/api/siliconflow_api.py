# api/siliconflow_api.py
from typing import Optional, Dict, Any
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)


class AsyncSiliconFlowChatClient:
    def __init__(self, api_key: str, default_model: str = "deepseek-ai/DeepSeek-V2-Chat"):
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = "https://api.siliconflow.cn/v1"
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
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
            self.logger.info(f"SiliconFlow客户端已初始化，模型: {self.default_model}")

    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("SiliconFlow客户端已关闭")

    async def chat(self, user_name: str, message: str, model: Optional[str] = None,
                  system_prompt: Optional[str] = None, temperature: float = 0.7,
                  max_tokens: int = 1000) -> Dict[str, Any]:
        """发送聊天请求到 SiliconFlow API"""
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
                
                # 构建 SiliconFlow 请求格式（兼容 OpenAI 格式）
                messages = self._build_messages(full_message, system_prompt)
                
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": max(0.0, min(2.0, temperature)),
                    "max_tokens": max(1, min(4096, max_tokens)),
                    "stream": False
                }

                async with self.session.post(f"{self.base_url}/chat/completions", json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        ai_response = self._extract_response(result)
                        self._update_conversation_history(full_message, ai_response)
                        return {"success": True, "response": ai_response}
                    else:
                        error_text = await resp.text()
                        self.logger.error(f"SiliconFlow API错误: {resp.status} - {error_text}")
                        return {"success": False, "error": f"API错误: {resp.status}", "response": None}
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"网络请求失败: {e}")
                return {"success": False, "error": f"网络错误: {str(e)}", "response": None}
            except Exception as e:
                self.logger.error(f"聊天处理异常: {e}")
                return {"success": False, "error": f"处理异常: {str(e)}", "response": None}

    def _build_messages(self, message: str, system_prompt: Optional[str]) -> list:
        """构建 SiliconFlow 格式的消息列表"""
        messages = []
        
        # 添加系统提示（如果有）
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加对话历史
        messages.extend(self.conversation_history)
        
        # 添加当前消息
        messages.append({"role": "user", "content": message.strip()})
        
        return messages

    def _extract_response(self, result: Dict) -> str:
        """从 SiliconFlow 响应中提取文本"""
        try:
            if "choices" in result and result["choices"]:
                choice = result["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return choice["message"]["content"].strip()
            
            self.logger.error(f"无法解析 SiliconFlow 响应: {result}")
            return "抱歉，我无法生成回复。"
        except Exception as e:
            self.logger.error(f"解析 SiliconFlow 响应失败: {e}")
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
            
            async with self.session.get(f"{self.base_url}/models") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = []
                    for model in data.get("data", []):
                        models.append({
                            "name": model["id"],
                            "display_name": model.get("name", model["id"]),
                            "owner": model.get("owned_by", "unknown")
                        })
                    return models
                else:
                    self.logger.error(f"获取模型列表失败: {resp.status}")
                    return []
        except Exception as e:
            self.logger.error(f"获取模型列表异常: {e}")
            return []