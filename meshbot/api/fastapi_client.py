# api/fastapi_client.py
from typing import Optional, Dict, Any, List, Callable
import aiohttp
import asyncio
import logging
import time
import uuid
import json
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class AsyncFastAPIChatClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logger
        self._lock = asyncio.Lock()
        self.conversation_history = []
        
        # 用于存储异步回调处理器
        self.message_handlers: List[Callable[[Any], Any]] = []
        
        # 用于请求-响应匹配（模拟 WebSocket 的 request_id 机制）
        self._pending_requests: Dict[str, asyncio.Future] = {}

    async def init(self):
        """异步初始化 session"""
        if self.session is None or self.session.closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
                
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            )
            self.logger.info(f"FastAPI客户端已初始化，服务端: {self.base_url}")

    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("FastAPI客户端已关闭")
            
        # 取消所有待处理的请求
        for request_id, future in self._pending_requests.items():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()

    async def chat(self, user_name: str, message: str, model: Optional[str] = None,
                  system_prompt: Optional[str] = None, temperature: float = 0.7,
                  max_tokens: int = 1000) -> Dict[str, Any]:
        """发送聊天请求到 FastAPI 服务端"""
        if not message or not message.strip():
            return {"success": False, "error": "消息内容为空", "response": None}

        async with self._lock:
            try:
                await self.init()
                
                if self.session is None:
                    self.logger.error("aiohttp.ClientSession 未初始化")
                    return {"success": False, "error": "客户端未初始化", "response": None}
                
                # 构建请求数据
                request_data = {
                    "user_name": user_name,
                    "message": message.strip(),
                    "system_prompt": system_prompt,
                    "temperature": max(0.0, min(2.0, temperature)),
                    "max_tokens": max(1, min(4096, max_tokens)),
                    "request_id": str(uuid.uuid4()),  # 用于跟踪请求
                    "timestamp": time.time()
                }
                
                # 添加对话历史（如果服务端支持）
                if self.conversation_history:
                    request_data["conversation_history"] = self.conversation_history

                # 发送 POST 请求到聊天端点
                url = urljoin(self.base_url, "/api/chat")
                async with self.session.post(url, json=request_data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        
                        # 处理响应
                        if result.get("success", False):
                            ai_response = result.get("response", "")
                            self._update_conversation_history(
                                f"{user_name}: {message}", 
                                ai_response
                            )
                            
                            # 调用消息处理器（异步通知）
                            asyncio.create_task(self._call_handlers(result))
                            
                            return {
                                "success": True, 
                                "response": ai_response,
                                "raw_response": result
                            }
                        else:
                            error_msg = result.get("error", "未知错误")
                            self.logger.error(f"FastAPI 服务端返回错误: {error_msg}")
                            return {
                                "success": False, 
                                "error": error_msg, 
                                "response": None
                            }
                    else:
                        error_text = await resp.text()
                        self.logger.error(f"FastAPI HTTP错误: {resp.status} - {error_text}")
                        return {
                            "success": False, 
                            "error": f"HTTP错误: {resp.status}", 
                            "response": None
                        }
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"网络请求失败: {e}")
                return {"success": False, "error": f"网络错误: {str(e)}", "response": None}
            except Exception as e:
                self.logger.error(f"聊天处理异常: {e}")
                return {"success": False, "error": f"处理异常: {str(e)}", "response": None}

    async def stream_chat(self, user_name: str, message: str, 
                         system_prompt: Optional[str] = None,
                         callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """流式聊天（如果服务端支持）"""
        try:
            await self.init()
            
            request_data = {
                "user_name": user_name,
                "message": message.strip(),
                "system_prompt": system_prompt,
                "stream": True
            }
            
            url = urljoin(self.base_url, "/api/chat/stream")
            if self.session is None or self.session.closed:
                self.logger.error("aiohttp.ClientSession 未初始化")
                return {"success": False, "error": "客户端未初始化", "response": None}
            async with self.session.post(url, json=request_data) as resp:
                if resp.status == 200:
                    full_response = ""
                    
                    # 处理流式响应
                    async for line in resp.content:
                        if line:
                            try:
                                chunk = line.decode('utf-8').strip()
                                if chunk.startswith('data: '):
                                    json_str = chunk[6:]  # 移除 'data: ' 前缀
                                    if json_str:
                                        data = json.loads(json_str)
                                        chunk_text = data.get("content", "")
                                        full_response += chunk_text
                                        
                                        # 调用回调函数
                                        if callback:
                                            callback(chunk_text)
                            except Exception as e:
                                self.logger.debug(f"解析流式数据失败: {e}")
                                continue
                    
                    self._update_conversation_history(
                        f"{user_name}: {message}", 
                        full_response
                    )
                    
                    return {"success": True, "response": full_response}
                else:
                    error_text = await resp.text()
                    self.logger.error(f"发生错误: {error_text}")
                    return {
                        "success": False, 
                        "error": f"HTTP错误: {resp.status}", 
                        "response": None
                    }
                    
        except Exception as e:
            self.logger.error(f"流式聊天失败: {e}")
            return {"success": False, "error": f"流式处理异常: {str(e)}", "response": None}

    def _update_conversation_history(self, user_message: str, ai_response: str):
        """更新对话历史"""
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": ai_response})
        
        # 限制历史记录长度
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
            
            url = urljoin(self.base_url, "/api/models")
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("models", [])
                else:
                    self.logger.error(f"获取模型列表失败: {resp.status}")
                    return []
        except Exception as e:
            self.logger.error(f"获取模型列表异常: {e}")
            return []

    async def get_health(self) -> Dict[str, Any]:
        """检查服务端健康状态"""
        try:
            await self.init()
            url = urljoin(self.base_url, "/health")
            if self.session is None or self.session.closed:
                self.logger.error("aiohttp.ClientSession 未初始化")
                return {"status": "error", "error": "客户端未初始化"}
            async with self.session.get(url) as resp:
                return {
                    "status": "healthy" if resp.status == 200 else "unhealthy",
                    "status_code": resp.status,
                    "response": await resp.text() if resp.status != 200 else None
                }
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return {"status": "error", "error": str(e)}

    async def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """通用消息发送方法（兼容 WebSocket 接口）"""
        return await self.chat(
            user_name=message.get("user", "unknown"),
            message=message.get("message", ""),
            system_prompt=message.get("system_prompt")
        )

    def add_message_handler(self, handler: Callable[[Any], Any]):
        """添加消息处理器（用于异步通知）"""
        if handler not in self.message_handlers:
            self.message_handlers.append(handler)
            self.logger.debug(f"已添加消息处理器，当前数量: {len(self.message_handlers)}")

    def remove_message_handler(self, handler: Callable[[Any], Any]):
        """移除消息处理器"""
        if handler in self.message_handlers:
            self.message_handlers.remove(handler)
            self.logger.debug(f"已移除消息处理器，当前数量: {len(self.message_handlers)}")

    async def _call_handlers(self, data: Any):
        """调用所有注册的消息处理器"""
        for handler in self.message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    # 在线程池中运行同步处理器
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, handler, data)
            except Exception as e:
                self.logger.error(f"消息处理器错误: {e}")

    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态（兼容 WebSocket 接口）"""
        return {
            "is_connected": self.session is not None and not self.session.closed,
            "is_running": True,
            "base_url": self.base_url,
            "message_handlers_count": len(self.message_handlers),
            "conversation_history_length": len(self.conversation_history)
        }