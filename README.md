# 消息合并器 (Message Merger)

<div align="center">
  <p>✨ 一个智能的消息合并插件，提升 AstrBot 对话体验 ✨</p>
  
  [![License](https://img.shields.io/github/license/YCHDDZZ/astrbot_plugin_message_merger)](LICENSE)
  [![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/YCHDDZZ/astrbot_plugin_message_merger/releases)
  [![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.16-green)](https://github.com/KroMio/AstrBot)
  
</div>

## 📖 简介

消息合并器是一个专为 AstrBot 设计的智能插件，使用轻量级 AI 模型判断短期连续消息是否需要合并，从而显著提升对话的流畅性和体验感。

### 🎯 核心功能

- **智能消息合并** - 自动识别并合并用户的连续短消息
- **上下文感知** - 结合历史对话进行综合判断
- **灵活配置** - 支持自定义模型、时间和消息数量阈值
- **无缝集成** - 与 AstrBot 完美兼容

## 🚀 安装

### 方法一：通过 AstrBot 插件管理器
```bash
# 在 AstrBot 控制台执行
plugin install https://github.com/YCHDDZZ/astrbot_plugin_message_merger.git
```

### 方法二：手动安装
1. 下载插件到 AstrBot 的 `plugins` 目录
2. 重启 AstrBot
3. 插件将自动加载

## ⚙️ 配置说明

插件提供丰富的配置选项，可通过 AstrBot 配置界面或直接编辑配置文件进行设置：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | Boolean | `true` | 是否启用插件 |
| `judge_provider_id` | String | `""` | 用于判断的模型提供商 ID |
| `judge_prompt` | Text | 见下方 | 判断消息完整性的 Prompt |
| `timeout_seconds` | Integer | `3` | 消息合并超时时间（秒） |
| `max_messages` | Integer | `5` | 最大合并消息数 |

### 🤖 默认 Prompt
```
你是一个句子完整性判断助手。请判断用户是否说完了一句完整的话。

注意：
1. 如果用户的话明显只说了一半（以"然后"、"还有"、"而且"、"比如"结尾，或明显是断句），则是不完整。
2. 如果用户的话表达了完整的意思，无论是否有标点，都是完整的。

用户的话：{text}

最近对话历史:
- {history}

请只回复 "完整" 或 "不完整"。
```

## 💡 使用场景

### 📝 示例 1：分段输入长文本
**用户输入（分段）：**
```
[15:30:01] 我今天去了公园，看到了很多
[15:30:02] 美丽的花朵，还有蝴蝶在花丛中飞舞
```

**插件处理后：**
```
[15:30:03] 我今天去了公园，看到了很多美丽的花朵，还有蝴蝶在花丛中飞舞
```

### 🗣️ 示例 2：快速提问
**用户输入（分段）：**
```
[15:32:10] 你知道
[15:32:11] 人工智能的未来
[15:32:12] 发展会怎么样吗
```

**插件处理后：**
```
[15:32:13] 你知道人工智能的未来发展会怎么样吗
```

## 🔧 高级配置

### 使用自定义模型
您可以在 `judge_provider_id` 中指定任意已在 AstrBot 中配置的模型，如：
- `openai/gpt-3.5-turbo`
- `openai/gpt-4`
- `anthropic/claude-3-haiku`
- 或其他支持的模型提供商

### 调整合并策略
- **减少 `timeout_seconds`** - 更快的合并响应
- **增加 `max_messages`** - 允许合并更多消息
- **自定义 `judge_prompt`** - 调整判断逻辑

## 🛠️ 开发与贡献

欢迎提交 Issue 和 Pull Request！

### 本地开发
```bash
# 克隆仓库
git clone https://github.com/YCHDDZZ/astrbot_plugin_message_merger.git

# 安装到 AstrBot
cp -r astrbot_plugin_message_merger /path/to/astrbot/plugins/
```

## 📄 许可证

本项目基于 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

感谢 AstrBot 团队提供的优秀框架，使得插件开发变得简单高效。

---

<div align="center">

**⭐ 如果这个插件对您有帮助，请给个 Star！**

</div>