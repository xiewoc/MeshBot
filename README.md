<div align="center">

**简体中文** | [ **English** ](README_EN.md)

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

所有处理在本地完成，隐私可控。

## ⚙️ 技术实现

- 使用 Python 监听 Meshtastic 设备的串口消息
- 当收到发给本节点的私信时，提取内容
- 调用本地运行的 Ollama 服务（或其他 AI 接口）
- 生成回复后通过同一网络回传

## 技术规格
| 连接方式 | 串口 |
| ----- | -----|
| 记忆 | 未实现|
| LLM Tool | 未实现 |
| 语言支持 | 中、英、日、法、俄、韩、西、德|
| 服务提供商 | OpenAI（及类似，如：DeepSeek、Ollama）、web sockets、fastapi|

### 当前配置示例

```json
{
  "platform": "ollama",
  "localization":{
      "language": "zh_CN"
  },
  "api_keys": {
    "openai": "your-openai-api-key",
    "deepseek": "your-deepseek-api-key",
    "openrouter": "your-openrouter-api-key",
    "gemini": "your-gemini-api-key",
    "claude": "your-claude-api-key",
    "siliconflow": "your-siliconflow-api-key",
    "fastapi": "your-fastapi-token"
  },
  "model_settings": {
    "ollama": "qwen2.5:7b",
    "openai": "gpt-3.5-turbo",
    "deepseek": "deepseek-chat",
    "openrouter": "openai/gpt-3.5-turbo",
    "gemini": "gemini-pro",
    "claude": "claude-3-sonnet-20240229",
    "siliconflow": "deepseek-ai/DeepSeek-V2-Chat",
    "fastapi": "fastapi-default"
  },
  "service_urls": {
    "websockets": "ws://localhost:9238",
    "fastapi": "http://127.0.0.1:8000"
  }
}
```

>[!IMPORTANT]
>请在使用`openai`, `deepseek`等时将`your-api-key`改为你使用的api key
>
>如果你在使用OpenRouter，请参照[README_OPENROUTER](README_OPENROUTER.md)
>
>若要接入 `AstrBot` ，可以使用 [AstrBot适配器](https://github.com/xiewoc/astrbot_plugin_adapter_meshbot) (*推荐*)

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

   > 这会启动 Ollama 后台服务，默认监听 `11434` 端口。
   >
   > 注：Ollama 在首次请求时会自动下载并加载模型（如果未提前 pull）。确保设备有足够存储和内存。

5. 运行主程序：
   ```bash
   python main.py
   ```
6. 用另一台设备向它发送私信，等待回复。

>[!IMPORTANT]
>在运行主程序时请注意运行路径，运行路径需在项目文件夹下

## 🎈当前版本 

V 1.0.3 - pre 1

- 添加了`localization` ,支持了 `en`, `zh_CN`, `ru`, `jp`, `ko`, `es`, `de`

## 🌱 后续想法

- 引入上下文记忆，让对话更连贯
- 添加一个WebUI
- 添加LLM Tool
- 优化`api`文件夹

## 🙏 写在最后

这个项目不是为了替代任何人，也不是要做个多聪明的 AI。  
只是想在那些安静的地方，留一个能回应你的声音。

如果你也喜欢这种感觉，欢迎一起改进它。

同时感谢那些为该项目做出贡献的开发者，感谢你们的支持与付出。

祝你的 Meshtastic 节点在山野间稳定运行，每一条回复，都像一束悄悄亮起的信号灯。📡💡

探索愉快！✨
