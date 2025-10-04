<div align="center">

**简体中文** | [ **English** ](readme_eng.md)

</div>

# Mesh AI 助手

一个安静地待在 Mesh 网络里的 AI 小节点。  
你发消息给它，它会回你一句。

不张扬，不联网，也不需要服务器。  
只是当你在山里、在野外、在没有信号的地方，还能问一句“你觉得呢？”，然后收到一个回答。

## 🧩 它能做什么？

- 接收发给它的私信（点对点消息）
- 用本地 AI 模型生成简短回复
- 把回答原路传回，就像它一直在线等你

比如：
> 你：“明天适合徒步吗？”  
> 它：“天气晴，风力2级，适合。”

所有处理在本地完成，隐私可控，无需依赖云端。

## 📡 为什么做这个？

Meshtastic 让我们能在没有网络的地方通信，但消息始终是人对人。  
我在想：能不能有一个“听得懂话”的节点？不复杂，也不聪明，但能回应。

于是做了这个小东西——  
它不会主动说话，也不参与群聊。  
你找它，它就在。

## ⚙️ 技术实现

- 使用 Python 监听 Meshtastic 设备的串口消息
- 当收到发给本节点的私信时，提取内容
- 调用本地运行的 Ollama 服务（或其他 AI 接口）
- 生成回复后通过同一网络回传

### 启动方式

1. **启动 Ollama 服务**：
   ```bash
   ollama serve
   ```
   > 这会启动 Ollama 后台服务，默认监听 `11434` 端口。

2. （可选）提前下载模型：
   ```bash
   ollama pull qwen2.5:7b
   ```
   或使用其他轻量模型如 `phi3`、`tinyllama`。

3. 运行 AI 节点程序：
   ```bash
   python main.py
   ```

> 注：Ollama 在首次请求时会自动下载并加载模型（如果未提前 pull）。确保设备有足够存储和内存。

### 当前配置示例

```json
{
    "system": {
      "system_prompt": "你是一个助手,请用简洁的语言(小于200字符)回复。",
      "platform": "websocket",
      "max_response_length": 200,
      "message_queue_timeout": 1
    },
    "clients": {
      "ollama": {
        "module": "api.ollama_api",
        "class": "AsyncOllamaChatClient",
        "kwargs": {
          "default_model": "qwen2.5:7b"
        }
      },
      "openai": {
        "module": "api.openai_api",
        "class": "AsyncOpenAIChatClient",
        "kwargs": {
          "api_key": "your-api-key",
          "default_model": "gpt-3.5-turbo"
        }
      },
      "deepseek": {
        "module": "api.deepseek_api",
        "class": "AsyncDeepSeekChatClient",
        "kwargs": {
          "api_key": "your-api-key",
          "default_model": "deepseek-chat"
        }
      },
      "websocket": {
        "module": "platforms.ws_platform",
        "class": "AsyncWebSocketsClient",
        "kwargs": {
          "uri": "ws://localhost:9238"
        }
      },
      "openrouter": {
        "module": "api.openrouter_api",
        "class": "AsyncOpenRouterChatClient",
        "kwargs": {
          "app_name": "MeshBot"
        }
      }
    }
  }
```

>[!IMPORTANT]
>请在使用`openai`, `deepseek`时将`your-api-key`改为你使用的api key
>
>如果你在使用OpenRouter，请参照[README_OPENROUTER](README_OPENROUTER.md)

完全可以在树莓派 + TTGO T-Beam 上跑起来，边走边聊。

## 🛠️ 如何使用？

1. 准备一台运行 Python 的设备（如 Raspberry Pi）
2. 连接你的 Meshtastic 节点（如通过 USB）
3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
4. 启动 Ollama 服务：
   ```bash
   ollama serve
   ```
5. 运行主程序：
   ```bash
   python mesh_ai_bot.py
   ```
6. 用另一台设备向它发送私信，等待回复。

## 🎈当前版本

- 添加了 `OpenAI` 和 `DeepSeek` 的 api ，提供了 `WebSockets` 接口
- 优化了项目结构
- 支持了接入 `AstrBot`

## 🌱 后续想法

- 引入上下文记忆，让对话更连贯
- 用 YAML 配置，减少代码修改

## 🙏 写在最后

这个项目不是为了替代任何人，也不是要做个多聪明的 AI。  
只是想在那些安静的地方，留一个能回应你的声音。

如果你也喜欢这种感觉，欢迎一起改进它。

祝你的 Meshtastic 节点在山野间稳定运行，每一条回复，都像一束悄悄亮起的信号灯。📡💡


探索愉快！✨

