# 合发消息拆分插件

把文字+表情/图片的合发消息拆成两条独立消息发送，让机器人的回复更拟人。

## 效果

之前 bot 一条消息里既发文字又带表情：

> 哈哈太好笑了 😂

这个插件把它拆成两条：

> 哈哈太好笑了

然后紧接着单独发一个表情消息 😂。

看起来更像人类分开打字和发表情的习惯。

## 原理

钩住 `send_service.after_build_message` 这个 Hook（BLOCKING 模式）。在每条出站消息构建完成后、实际发送前：

1. 检查消息的 `raw_message` 是否同时包含 `type: "text"` 和 `type: "emoji"`（或 `type: "image"`）
2. 如果是，把文字部分保留在原消息中，继续正常发送
3. 把表情/图片部分用 `self.ctx.send.emoji()` / `self.ctx.send.image()` 单独发出

**防递归**：拆出的纯表情/图片消息不含文字组件，不满足拆分条件，不会再次触发拆分。

## 配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `plugin.enabled` | `true` | 总开关 |
| `plugin.config_version` | `"1.0.0"` | 配置文件版本 |
| `split.split_emoji` | `true` | 拆分文字+表情 |
| `split.split_image` | `false` | 拆分文字+图片（默认关，图片通常需要依赖文字上下文） |

config.toml：

```toml
[plugin]
config_version = "1.0.0"
enabled = true

[split]
split_emoji = true
split_image = false
```

## 开发

```
maibot_plugin_split-rich-message/
├── _manifest.json     # 插件清单
├── plugin.py          # 核心逻辑
├── config.toml        # 默认配置
└── README.md
```

SDK 插件，遵循 `maibot-plugin-sdk` 规范。

## License

MIT
