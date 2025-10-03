from typing import Optional, Dict, Any
import aiohttp
import asyncio
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AsyncOllamaChatClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", default_model: str = "qwen2.5:7b"):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.conversation_history = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logger
        self._lock = asyncio.Lock()

    async def init(self):
        """异步初始化 session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=120)
            )
            self.logger.info(f"Ollama客户端已初始化，模型: {self.default_model}")

    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("Ollama客户端已关闭")

    async def chat(self, user_name: str, message: str, model: Optional[str] = None, 
                  system_prompt: Optional[str] = None, temperature: float = 0.7, 
                  max_tokens: int = 1000) -> Dict[str, Any]:
        """发送聊天请求"""
        if not message or not message.strip():
            return {"success": False, "error": "消息内容为空", "response": None}

        async with self._lock:
            try:
                await self.init()
                
                if self.session is None:
                    self.logger.error("aiohttp.ClientSession 未初始化")
                    return {"success": False, "error": "客户端未初始化", "response": None}
                
                model = model or self.default_model
                message = f"{user_name}:{message}"
                messages = self._build_messages(message, system_prompt)
                
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": max(0.1, min(1.0, temperature)),
                        "num_predict": max(10, min(4000, max_tokens)),
                        "num_ctx": 4096
                    }
                }

                async with self.session.post(f"{self.base_url}/api/chat", json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        ai_response = result["message"]["content"]
                        self._update_conversation_history(message, ai_response)
                        return {"success": True, "response": ai_response}
                    else:
                        error_text = await resp.text()
                        self.logger.error(f"Ollama API错误: {resp.status} - {error_text}")
                        return {"success": False, "error": f"API错误: {resp.status}", "response": None}
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"网络请求失败: {e}")
                return {"success": False, "error": f"网络错误: {str(e)}", "response": None}
            except Exception as e:
                self.logger.error(f"聊天处理异常: {e}")
                return {"success": False, "error": f"处理异常: {str(e)}", "response": None}

    def _build_messages(self, message: str, system_prompt: Optional[str]) -> list:
        """构建消息列表"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": message.strip()})
        return messages

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
                    raise Exception("aiohttp.ClientSession 未初始化")
            
            async with self.session.get(f"{self.base_url}/api/tags") as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("models", [])
        except Exception as e:
            self.logger.error(f"获取模型列表失败: {e}")
            return []
