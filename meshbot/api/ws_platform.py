import asyncio
import websockets
import json
import logging
import time
import uuid
from typing import Optional, Dict, Any, List, Callable, Union, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AsyncWebSocketsClient:
    def __init__(self, uri: str = "ws://localhost:9238"):
        self.uri = uri
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_running = False
        self.message_handlers: List[Callable[[Any], Any]] = []
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 1
        self.max_reconnect_delay = 30
        self.logger = logger
        self._lock = asyncio.Lock()
        
        # 👉 新增：存储待处理的请求响应（request_id -> (event, [data])）
        self._pending_responses: Dict[str, Tuple[asyncio.Event, list]] = {}

    async def init(self):
        """异步初始化 WebSocket 连接"""
        if self.is_connected and self.websocket and not self.websocket.closed:
            return True
            
        async with self._lock:
            try:
                self.websocket = await websockets.connect(
                    self.uri, 
                    ping_interval=20, 
                    ping_timeout=10
                )
                self.is_connected = True
                self.reconnect_attempts = 0
                self.logger.info(f"WebSocket客户端已初始化，连接: {self.uri}")
                return True
            except Exception as e:
                self.logger.error(f"WebSocket连接失败: {e}")
                return False

    async def close(self):
        """关闭 WebSocket 连接"""
        async with self._lock:
            self.is_running = False
            self.is_connected = False
            
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()
                self.logger.info("WebSocket客户端已关闭")

    async def start(self):
        """启动客户端并开始处理消息"""
        if self.is_running:
            self.logger.warning("客户端已在运行中")
            return

        self.is_running = True
        success = await self._connect_with_retry()
        
        if success:
            # 启动消息接收任务
            asyncio.create_task(self._receive_messages())
            self.logger.info("WebSocket客户端已启动")
        else:
            self.logger.error("WebSocket客户端启动失败")

    async def _connect_with_retry(self) -> bool:
        """带重试机制的连接方法"""
        while self.is_running and not self.is_connected:
            success = await self.init()
            
            if success:
                return True
                
            self.reconnect_attempts += 1
            
            if self.reconnect_attempts > self.max_reconnect_attempts:
                self.logger.error(f"达到最大重连次数 ({self.max_reconnect_attempts})，停止重连")
                return False
                
            delay = min(
                self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 
                self.max_reconnect_delay
            )
            
            self.logger.info(f"第 {self.reconnect_attempts} 次重连，{delay} 秒后重试...")
            await asyncio.sleep(delay)
        
        return self.is_connected

    async def _ensure_connection(self):
        """确保连接正常，如果断开则自动重连"""
        if not self.is_connected and self.is_running:
            self.logger.info("连接断开，尝试重连...")
            await self._connect_with_retry()

    async def _receive_messages(self):
        """持续接收消息"""
        while self.is_running:
            if not self.is_connected:
                await self._ensure_connection()
                if not self.is_connected:
                    await asyncio.sleep(1)
                    continue
            
            try:
                if self.websocket:
                    raw_message = await self.websocket.recv()
                    
                    if not self.is_running:
                        break
                        
                    message_str = self._ensure_string(raw_message)
                    if message_str:
                        await self._handle_message(message_str)
                        
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("WebSocket连接已关闭")
                self.is_connected = False
                
            except Exception as e:
                self.logger.error(f"接收消息错误: {e}")
                self.is_connected = False
                await asyncio.sleep(1)  # 防止风暴
            
            # 防止 CPU 占用过高
            await asyncio.sleep(0.1)

    def _ensure_string(self, raw_message: Any) -> Optional[str]:
        """确保消息为字符串类型"""
        try:
            if isinstance(raw_message, str):
                return raw_message
            elif isinstance(raw_message, (bytes, bytearray)):
                return raw_message.decode('utf-8')
            elif isinstance(raw_message, memoryview):
                return raw_message.tobytes().decode('utf-8')
            else:
                self.logger.warning(f"未知的消息类型: {type(raw_message)}")
                return str(raw_message)
                
        except UnicodeDecodeError:
            self.logger.error("消息解码错误: 无法将字节解码为UTF-8")
            return None
        except Exception as e:
            self.logger.error(f"消息转换错误: {e}")
            return None

    async def _handle_message(self, message: str):
        """处理接收到的字符串消息"""
        try:
            data = json.loads(message)
            self.logger.debug(f"接收JSON: {data}")

            # 👉 优先检查是否是响应消息（通过 request_id 匹配）
            if isinstance(data, dict):
                request_id = data.get('request_id')
                if request_id and request_id in self._pending_responses:
                    event, data_holder = self._pending_responses[request_id]
                    data_holder[0] = data  # 存入响应数据
                    event.set()           # 触发等待
                    self.logger.debug(f"✅ 响应已匹配并触发: request_id={request_id}")
                    return  # 不再广播给普通处理器（避免重复处理）

            # 👉 转发给所有注册的处理器
            await self._call_handlers(data)
            
        except json.JSONDecodeError:
            self.logger.debug(f"接收文本: {message}")
            await self._call_handlers(message)

    async def _call_handlers(self, data: Any):
        """调用所有注册的消息处理器"""
        loop = asyncio.get_running_loop()
        for handler in self.message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    # await coroutine handlers
                    await handler(data)
                else:
                    # run blocking/sync handlers in threadpool to avoid blocking receive loop
                    await loop.run_in_executor(None, handler, data)
            except Exception as e:
                self.logger.error(f"消息处理器错误: {e}")

    async def send_message(self, message: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """发送消息"""
        if not message:
            return {"success": False, "error": "消息内容为空"}

        async with self._lock:
            try:
                # Ensure the client is started and connected. If the client was not started
                # we try to start it so send/receive can work as expected.
                if not self.is_running:
                    # start will attempt to connect and spawn the receive loop
                    await self.start()
                else:
                    await self._ensure_connection()

                if not self.is_connected or not self.websocket:
                    self.logger.error("WebSocket未连接")
                    return {"success": False, "error": "WebSocket未连接"}
                
                if isinstance(message, dict):
                    message_str = json.dumps(message)
                else:
                    message_str = str(message)
                
                await self.websocket.send(message_str)
                self.logger.debug(f"发送消息: {message}")
                return {"success": True, "response": "消息发送成功"}
            
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("连接已关闭，无法发送消息")
                self.is_connected = False
                return {"success": False, "error": "连接已关闭"}
            except Exception as e:
                self.logger.error(f"发送消息错误: {e}")
                self.is_connected = False
                return {"success": False, "error": f"发送失败: {str(e)}"}

    async def chat(self, user_name: str, message: str, system_prompt: str, timeout: float = 30.0) -> Dict[str, Any]:
        """
        发送聊天消息并等待响应
        
        Args:
            user_name: 用户名
            message: 聊天消息
            system_prompt: 占位（可忽略或用于上下文）
            timeout: 超时时间（秒）
            
        Returns:
            包含成功状态和响应数据的字典
        """
        if not user_name or not message or not message.strip():
            return {"success": False, "error": "用户名或消息内容为空", "response": None}

        try:
            # Ensure connection and receive loop are running so we can get the response
            if not self.is_running:
                await self.start()
            else:
                await self._ensure_connection()

            if not self.is_connected:
                return {"success": False, "error": "WebSocket未连接", "response": None}
            
            # 👉 生成唯一请求ID
            request_id = str(uuid.uuid4())
            chat_data = {
                "type": "chat",
                "user": user_name,
                "message": message.strip(),
                "timestamp": time.time(),
                "request_id": request_id  # 关键：用于响应匹配
            }
            
            # 👉 创建本次请求的等待事件和数据容器
            response_event = asyncio.Event()
            response_data = [None]  # 使用列表以便在闭包中修改
            self._pending_responses[request_id] = (response_event, response_data)
            
            # 👉 发送消息
            send_result = await self.send_message(chat_data)
            if not send_result["success"]:
                self._pending_responses.pop(request_id, None)
                return send_result
            
            self.logger.info(f"已发送聊天消息: {user_name}: {message} [ID: {request_id}]")
            
            # 👉 等待服务器响应
            try:
                await asyncio.wait_for(response_event.wait(), timeout=timeout)
                raw_response = response_data[0]
                
                if isinstance(raw_response, dict):
                    response_content = raw_response.get('message', '收到响应但无消息内容')
                else:
                    response_content = str(raw_response)
                    
                return {
                    "success": True, 
                    "response": response_content,
                    "raw_response": raw_response
                }
            except asyncio.TimeoutError:
                self.logger.warning(f"等待聊天响应超时 [ID: {request_id}]")
                return {"success": False, "error": "等待响应超时", "response": None}
            finally:
                # 👉 清理待响应映射
                self._pending_responses.pop(request_id, None)
        
        except Exception as e:
            self.logger.error(f"聊天消息发送失败: {e}")
            return {"success": False, "error": f"处理异常: {str(e)}", "response": None}

    def add_message_handler(self, handler: Callable[[Any], Any]):
        """添加消息处理器"""
        if handler not in self.message_handlers:
            self.message_handlers.append(handler)
            self.logger.debug(f"已添加消息处理器，当前数量: {len(self.message_handlers)}")

    def remove_message_handler(self, handler: Callable[[Any], Any]):
        """移除消息处理器"""
        if handler in self.message_handlers:
            self.message_handlers.remove(handler)
            self.logger.debug(f"已移除消息处理器，当前数量: {len(self.message_handlers)}")

    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        return {
            "is_connected": self.is_connected,
            "is_running": self.is_running,
            "reconnect_attempts": self.reconnect_attempts,
            "message_handlers_count": len(self.message_handlers),
            "pending_requests": len(self._pending_responses),  # 新增：待响应请求数
            "uri": self.uri
        }