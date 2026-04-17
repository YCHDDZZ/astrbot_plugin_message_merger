<div align="center">

# 🤖 AstrBot 消息合并插件

<p align="center">
  <strong>智能消息合并，提升对话体验</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/AstrBot->=4.16-blue" alt="AstrBot Version">
  <img src="https://img.shields.io/badge/Python-3.8+-blue" alt="Python Version">
  <img src="https://img.shields.io/github/license/YCHDDZZ/astrbot_plugin_message_merger" alt="License">
</p>

</div>

---

## ✨ 功能特性

- **智能消息合并**：自动检测并合并连续的短消息，提升对话连贯性
- **灵活配置**：支持在管理面板中自定义各项参数
- **模型定制**：可指定特定的模型提供商和模型ID
- **时间控制**：可设置合并时间长度（秒）
- **数量限制**：可设置最多合并消息条数
- **调试支持**：提供调试日志功能便于问题排查
- **自动清理**：定时清理过期缓存，节省内存资源

## 📋 配置说明

插件提供丰富的配置选项，可在 AstrBot 管理面板中进行设置：

### 🔧 基础配置
- **启用插件**：控制插件是否生效

### 🧠 模型配置
- **模型提供商 ID**：用于判断消息完整性的模型提供商（例如：openai）
- **具体模型 ID**：指定的具体模型名称（例如：gpt-3.5-turbo，留空则使用默认模型）
- **判断 Prompt**：自定义判断消息完整性的提示词模板

### ⏱️ 合并配置
- **合并时间长度**：设置超时时间（秒），超时后自动合并发送（1-60秒）
- **最多合并消息条数**：限制一次最多合并的消息数量（1-20条）

### ⚙️ 高级配置
- **启用调试日志**：开启详细日志输出
- **自动清理间隔**：设置自动清理缓存的时间间隔（5-240分钟）

## 🛠️ 安装方法

### 方式一：通过 Git Clone
```bash
cd your_astrbot/plugins
git clone https://github.com/YCHDDZZ/astrbot_plugin_message_merger.git
```

### 方式二：手动下载
1. 下载插件压缩包
2. 解压到 AstrBot 的插件目录
3. 重启 AstrBot

## 🚀 使用方法

1. 安装插件后重启 AstrBot
2. 进入管理面板 → 插件管理 → 消息合并器 → 配置
3. 根据需要调整各项参数
4. 保存配置并启用插件

## 📖 工作原理

1. **消息收集**：插件收集来自同一用户的连续消息
2. **完整性判断**：使用配置的模型判断消息是否完整
3. **定时合并**：如果达到超时时间或最大消息数，则合并消息
4. **智能放行**：只有当消息被判断为完整时才放行给后续处理器

## 📁 项目结构

```
astrbot_plugin_message_merger/
├── main.py              # 插件主入口文件
├── _conf_schema.json    # 配置模式定义
├── metadata.yaml        # 插件元数据
├── README.md            # 项目说明文档
└── assets/              # 资源文件目录
```

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request 来改进插件功能！

### 开发环境搭建
```bash
# 克隆项目
git clone https://github.com/YCHDDZZ/astrbot_plugin_message_merger.git
cd astrbot_plugin_message_merger

# 开发和测试
# 修改代码后在 AstrBot 中测试
```

### 代码规范
- 遵循 PEP 8 编码规范
- 保持代码简洁易读
- 添加必要的注释

## 📝 更新日志

### v1.0.0
- 实现基础消息合并功能
- 添加模型完整性判断
- 支持自定义配置参数
- 添加自动清理机制

## 📜 许可证

MIT License - 详见 [LICENSE](./LICENSE) 文件

## 🆘 技术支持

- **作者**：YCHDDZZ
- **版本**：1.0.0
- **AstrBot 版本要求**：>=4.16
- **问题反馈**：[GitHub Issues](https://github.com/YCHDDZZ/astrbot_plugin_message_merger/issues)

## 💡 使用场景

- **连续输入优化**：当用户分多次发送一条完整信息时，自动合并为一条消息
- **对话流畅性提升**：减少因网络延迟或用户习惯导致的碎片化消息
- **上下文保持**：确保 AI 模型获得完整的输入信息
- **用户体验改善**：让机器人对话更加自然流畅

---

<div align="center">

**⭐ 如果这个插件对你有帮助，请给个 Star！**

</div>