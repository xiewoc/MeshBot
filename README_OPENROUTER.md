# OpenRouter 集成指南

## 什么是 OpenRouter？

OpenRouter 是一个统一的 AI API 网关，提供对 400+ 个 AI 模型的访问，包括来自 Google、Meta、Mistral、DeepSeek 等厂商的**免费模型**。

### 为什么选择 OpenRouter？

1. **免费模型丰富**：提供多个高质量免费模型（如 Gemini 2.0 Flash、Llama 4 Maverick 等）
2. **统一接口**：一个 API key 访问所有模型，无需注册多个平台
3. **自动负载均衡**：自动选择最快的可用端点
4. **透明计费**：按实际使用付费，免费模型每天 50-1000 次请求额度

## 快速开始

### 1. 获取 OpenRouter API Key

1. 访问 [https://openrouter.ai/keys](https://openrouter.ai/keys)
2. 登录或注册账号
3. 创建新的 API key
4. 复制 API key（格式：`sk-or-v1-xxx...`）

### 2. 配置 MeshBot

#### 方式一：使用 .env 文件（推荐）

```bash
# 1. 复制环境变量模板
cp .env.example .env

# 2. 编辑 .env 文件，填入你的 API key
nano .env
```

在 `.env` 中添加：
```bash
# OpenRouter 配置
OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here

# 可选：指定默认模型（不设置则自动使用免费模型）
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
```

#### 方式二：在 config.json 中硬编码（不推荐）

```json
{
  "clients": {
    "openrouter": {
      "module": "api.openrouter_api",
      "class": "AsyncOpenRouterChatClient",
      "kwargs": {
        "api_key": "sk-or-v1-xxx",
        "default_model": "google/gemini-2.0-flash-exp:free"
      }
    }
  }
}
```

### 3. 选择 OpenRouter 作为默认平台

编辑 `config.json`：
```json
{
  "system": {
    "platform": "openrouter",
    "system_prompt": "你是一个助手，请用简洁的语言(小于200字符)回复。",
    "max_response_length": 200
  }
}
```

### 4. 运行 MeshBot

```bash
# 安装依赖（如果还没安装）
pip install -r requirements.txt

# 启动机器人
python main.py
```

## 推荐的免费模型

以下是 2025 年表现优秀的免费模型（按 top-weekly 排序）：

### 1. **Google Gemini 2.0 Flash Exp** (推荐)
- **模型 ID**: `google/gemini-2.0-flash-exp:free`
- **特点**: 速度快、质量高、支持长上下文
- **适用场景**: 通用对话、问答、简短任务

### 2. **Meta Llama 4 Maverick**
- **模型 ID**: `meta-llama/llama-4-maverick:free`
- **特点**: 400B 参数 MoE 模型，256K 上下文
- **适用场景**: 复杂推理、长文本处理

### 3. **Mistral Small 3.1**
- **模型 ID**: `mistralai/mistral-small-3.1:free`
- **特点**: 24B 参数，96K 上下文，多模态支持
- **适用场景**: 多语言对话、编程任务

### 4. **DeepSeek V3**
- **模型 ID**: `deepseek/deepseek-chat:free`
- **特点**: 代码能力强、推理优秀
- **适用场景**: 编程辅助、逻辑推理

### 5. **Kimi-VL-A3B-Thinking**
- **模型 ID**: `moonshot/kimi-vl-a3b-thinking:free`
- **特点**: 轻量级 MoE，131K 上下文
- **适用场景**: 轻量级部署、快速响应

## 模型选择策略

### 自动选择（推荐）

不在 `.env` 中设置 `OPENROUTER_MODEL`，MeshBot 会自动使用：
```
google/gemini-2.0-flash-exp:free
```

### 手动指定

在 `.env` 中设置你喜欢的模型：
```bash
OPENROUTER_MODEL=meta-llama/llama-4-maverick:free
```

### 动态获取 Top 模型

使用 API 动态获取排名最高的免费模型：
```python
from api.openrouter_api import AsyncOpenRouterChatClient

async def get_best_model():
    client = AsyncOpenRouterChatClient()
    await client.init()
    top_model = await client.get_top_free_model()
    print(f"当前最佳免费模型: {top_model}")
    await client.close()
```

## 使用限制

### 免费模型速率限制

- **未购买积分**: 50 次请求/天
- **购买 ≥10 积分**: 1000 次请求/天

### Mesh 网络限制

由于 Meshtastic LoRa 传输限制：
- **最大响应长度**: 200 字符（已在 `config.json` 中配置）
- **建议系统提示**: 明确要求简短回复

示例系统提示（已配置）：
```
你是一个助手，请用简洁的语言(小于200字符)回复。
```

## 故障排查

### 问题 1: API Key 无效

**错误信息**: `401 Unauthorized` 或 `Invalid API key`

**解决方法**:
1. 检查 `.env` 中的 `OPENROUTER_API_KEY` 是否正确
2. 确认 API key 格式为 `sk-or-v1-...`
3. 访问 [https://openrouter.ai/keys](https://openrouter.ai/keys) 重新生成

### 问题 2: 模型未找到

**错误信息**: `404 Not Found` 或 `Model not available`

**解决方法**:
1. 检查模型 ID 是否正确（必须以 `:free` 结尾）
2. 访问 [OpenRouter 免费模型列表](https://openrouter.ai/models?q=(free)&order=top-weekly) 查看可用模型
3. 尝试使用默认模型：
   ```bash
   # 注释掉或删除 OPENROUTER_MODEL 配置
   # OPENROUTER_MODEL=...
   ```

### 问题 3: 超过速率限制

**错误信息**: `429 Too Many Requests` 或 `Rate limit exceeded`

**解决方法**:
1. 等待 24 小时后重试（免费配额每日重置）
2. 购买至少 10 积分提升至 1000 次/天
3. 切换到其他 AI 后端（Ollama 本地部署无限制）

### 问题 4: .env 文件未生效

**症状**: 设置了 `.env` 但仍提示未配置 API key

**解决方法**:
1. 确认 `.env` 文件在项目根目录（与 `main.py` 同级）
2. 检查 `.env` 文件权限（需要可读）
3. 确认已安装 `python-dotenv`：
   ```bash
   pip install python-dotenv
   ```
4. 重启 MeshBot 程序

## 高级配置

### 自定义 HTTP Headers

OpenRouter 支持自定义 headers 用于统计和排行榜展示：

```bash
# .env
OPENROUTER_SITE_URL=https://github.com/your-username/MeshBot
```

或在代码中：
```python
client = AsyncOpenRouterChatClient(
    app_name="MeshBot",
    site_url="https://your-project-url.com"
)
```

### 多模型切换

在运行时切换模型：
```python
# 使用特定模型
result = await client.chat(
    user_name="User",
    message="Hello",
    model="meta-llama/llama-4-maverick:free"
)
```

### 流式响应（实验性）

OpenRouter 支持流式响应（SSE），但 MeshBot 默认使用非流式模式以保证 LoRa 传输稳定性。

如需启用：
```python
result = await client.chat(
    user_name="User",
    message="Hello",
    stream=True  # 启用流式响应
)
```

## 最佳实践

1. **优先使用 .env 管理密钥**：避免在代码或 Git 中暴露 API key
2. **选择合适的免费模型**：根据任务复杂度选择（简单任务用 Gemini Flash，复杂任务用 Llama 4）
3. **控制响应长度**：LoRa 传输限制要求 ≤200 字符
4. **监控使用量**：免费配额有限，定期检查 [OpenRouter 仪表板](https://openrouter.ai/activity)
5. **本地备用方案**：配置 Ollama 作为备用（无网络时使用）

## 相关链接

- [OpenRouter 官网](https://openrouter.ai/)
- [API 文档](https://openrouter.ai/docs)
- [免费模型列表](https://openrouter.ai/models?q=(free)&order=top-weekly)
- [OpenRouter 排行榜](https://openrouter.ai/rankings)
- [定价说明](https://openrouter.ai/docs/pricing)

## 示例：完整配置

### .env 文件
```bash
# OpenRouter 配置
OPENROUTER_API_KEY=sk-or-v1-1234567890abcdefghijklmnopqrstuvwxyz
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
OPENROUTER_SITE_URL=https://github.com/myusername/MeshBot

# 系统配置
LOG_LEVEL=INFO
MAX_RESPONSE_LENGTH=200
```

### config.json 文件
```json
{
  "system": {
    "system_prompt": "你是一个助手，请用简洁的语言(小于200字符)回复。",
    "platform": "openrouter",
    "max_response_length": 200,
    "message_queue_timeout": 1
  },
  "clients": {
    "openrouter": {
      "module": "api.openrouter_api",
      "class": "AsyncOpenRouterChatClient",
      "kwargs": {
        "app_name": "MeshBot"
      }
    },
    "ollama": {
      "module": "api.ollama_api",
      "class": "AsyncOllamaChatClient",
      "kwargs": {
        "default_model": "qwen2.5:7b"
      }
    }
  }
}
```

### 启动命令
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
nano .env  # 填入你的 OPENROUTER_API_KEY

# 3. 启动 MeshBot
python main.py
```

---

**提示**: 如果遇到问题，请检查日志输出（带 emoji 的日志更易识别错误）：
- ✅ 成功
- ❌ 错误
- ⚠️ 警告
- 📡 消息接收
- 🤖 AI 回复