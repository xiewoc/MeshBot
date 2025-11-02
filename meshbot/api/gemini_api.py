# api/gemini_api.py
from typing import Optional, Dict, Any
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)


class AsyncGeminiChatClient:
    def __init__(self, api_key: str, default_model: str = "gemini-pro"):
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.conversation_history = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logger
        self._lock = asyncio.Lock()

    async def init(self):
        """异步初始化 session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
            self.logger.info(f"Gemini客户端已初始化，模型: {self.default_model}")

    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("Gemini客户端已关闭")

    async def chat(self, user_name: str, message: str, model: Optional[str] = None,
                  system_prompt: Optional[str] = None, temperature: float = 0.7,
                  max_tokens: int = 1000) -> Dict[str, Any]:
        """发送聊天请求到 Gemini API"""
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
                
                # 构建 Gemini 请求格式
                contents = self._build_contents(full_message, system_prompt)
                
                payload = {
                    "contents": contents,
                    "generationConfig": {
                        "temperature": max(0.0, min(1.0, temperature)),
                        "maxOutputTokens": max(1, min(8192, max_tokens)),
                        "topP": 0.8,
                        "topK": 40
                    }
                }

                url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
                
                async with self.session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        ai_response = self._extract_response(result)
                        self._update_conversation_history(full_message, ai_response)
                        return {"success": True, "response": ai_response}
                    else:
                        error_text = await resp.text()
                        self.logger.error(f"Gemini API错误: {resp.status} - {error_text}")
                        return {"success": False, "error": f"API错误: {resp.status}", "response": None}
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"网络请求失败: {e}")
                return {"success": False, "error": f"网络错误: {str(e)}", "response": None}
            except Exception as e:
                self.logger.error(f"聊天处理异常: {e}")
                return {"success": False, "error": f"处理异常: {str(e)}", "response": None}

    def _build_contents(self, message: str, system_prompt: Optional[str]) -> list:
        """构建 Gemini 格式的消息内容"""
        contents = []
        
        # 添加系统提示（如果有）
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": system_prompt}]
            })
            contents.append({
                "role": "model", 
                "parts": [{"text": "好的，我明白了。"}]
            })
        
        # 添加对话历史
        for msg in self.conversation_history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        
        # 添加当前消息
        contents.append({
            "role": "user",
            "parts": [{"text": message.strip()}]
        })
        
        return contents

    def _extract_response(self, result: Dict) -> str:
        """从 Gemini 响应中提取文本"""
        try:
            if "candidates" in result and result["candidates"]:
                candidate = result["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
            
            self.logger.error(f"无法解析 Gemini 响应: {result}")
            return "抱歉，我无法生成回复。"
        except Exception as e:
            self.logger.error(f"解析 Gemini 响应失败: {e}")
            return "抱歉，响应解析失败。"

    def _update_conversation_history(self, user_message: str, ai_response: str):
        """更新对话历史"""
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": ai_response})
        
        if len(self.conversation_history) > 10:  # Gemini 上下文较短
            self.conversation_history = self.conversation_history[-10:]
        self.logger.debug(f"对话历史更新，当前长度: {len(self.conversation_history)}")

    async def get_models(self) -> list:
        """获取可用模型列表"""
        try:
            await self.init()
            if self.session is None:
                self.logger.error("aiohttp.ClientSession 未初始化")
                return []
            
            url = f"{self.base_url}/models?key={self.api_key}"
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = []
                    for model in data.get("models", []):
                        if "generateContent" in model.get("supportedGenerationMethods", []):
                            models.append({
                                "name": model["name"],
                                "display_name": model["displayName"],
                                "version": model.get("version", "unknown")
                            })
                    return models
                else:
                    self.logger.error(f"获取模型列表失败: {resp.status}")
                    return []
        except Exception as e:
            self.logger.error(f"获取模型列表异常: {e}")
            return []