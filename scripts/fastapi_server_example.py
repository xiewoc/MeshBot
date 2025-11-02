# server/fastapi_server.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
import logging
import asyncio
import time

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MeshBot FastAPI Server", version="1.0.0")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求模型
class ChatRequest(BaseModel):
    user_name: str
    message: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    request_id: Optional[str] = None
    timestamp: Optional[float] = None
    conversation_history: Optional[List[Dict[str, str]]] = None

class ChatResponse(BaseModel):
    success: bool
    response: str
    error: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: float

# 模拟 AI 响应生成
async def generate_ai_response(user_name: str, message: str, system_prompt: Optional[str] = None) -> str:
    """模拟 AI 响应生成"""
    # 这里可以集成真实的 AI 模型
    prompt = system_prompt or "你是一个有用的助手。"
    
    # 模拟处理时间
    await asyncio.sleep(0.1)
    
    return f"你好 {user_name}！你说：'{message}'。这是一个来自 FastAPI 服务的回复。"

@app.get("/")
async def root():
    """根端点"""
    return {"message": "MeshBot FastAPI Server is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/api/models")
async def get_models():
    """获取可用模型列表"""
    models = [
        {"id": "fastapi-default", "name": "FastAPI Default Model", "type": "chat"},
        {"id": "fastapi-advanced", "name": "FastAPI Advanced Model", "type": "chat"},
    ]
    return {"models": models}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """聊天端点"""
    try:
        logger.info(f"收到聊天请求: {request.user_name}: {request.message}")
        
        # 生成 AI 响应
        ai_response = await generate_ai_response(
            request.user_name, 
            request.message, 
            request.system_prompt
        )
        
        response = ChatResponse(
            success=True,
            response=ai_response,
            request_id=request.request_id,
            timestamp=time.time()
        )
        
        logger.info(f"返回聊天响应: {ai_response}")
        return response
        
    except Exception as e:
        logger.error(f"聊天处理错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/stream")
async def stream_chat_endpoint(request: ChatRequest):
    """流式聊天端点（示例）"""
    from fastapi.responses import StreamingResponse
    import json
    
    async def generate_stream():
        """生成流式响应"""
        message = f"正在处理: {request.message}"
        chunks = [f"思考: {message}", f"回复: 你好 {request.user_name}!", "处理完成!"]
        
        for chunk in chunks:
            yield f"data: {json.dumps({'content': chunk})}\n\n"
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        generate_stream(), 
        media_type="text/plain"
    )

if __name__ == "__main__":
    uvicorn.run(
        "fastapi_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )