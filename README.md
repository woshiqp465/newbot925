# Telegram 整合机器人 - NewBot925 🤖

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-Latest-blue)](https://core.telegram.org/bots/api)

一个功能强大的Telegram机器人，集成了客服系统和搜索镜像功能。

## ✨ 核心功能

### 客服中转系统
- 🔄 **消息自动转发**：客户消息自动转发给管理员
- 💬 **便捷回复**：管理员直接回复转发消息即可回复客户
- 👥 **会话管理**：追踪和管理多个客户会话
- 📊 **实时统计**：消息数量、会话状态等统计信息

### 智能功能
- ⏰ **营业时间管理**：自动识别工作时间
- 🤖 **自动回复**：非工作时间自动回复
- 📝 **消息历史**：完整的对话记录存储
- 🏷️ **标签系统**：客户和会话标签管理

### 管理功能
- 📈 **统计仪表板**：查看详细统计信息
- 🔍 **会话监控**：实时查看活跃会话
- 📢 **广播消息**：向所有客户发送通知
- ⚙️ **动态配置**：运行时调整设置

## 🏗️ 系统架构

```
telegram-customer-bot/
├── src/
│   ├── core/           # 核心模块
│   │   ├── bot.py      # 主机器人类
│   │   ├── router.py   # 消息路由系统
│   │   └── handlers.py # 处理器基类
│   ├── modules/        # 功能模块
│   │   └── storage/    # 数据存储
│   ├── utils/          # 工具函数
│   │   ├── logger.py   # 日志系统
│   │   ├── exceptions.py # 异常处理
│   │   └── decorators.py # 装饰器
│   └── config/         # 配置管理
├── tests/              # 测试文件
├── logs/               # 日志文件
├── data/               # 数据存储
└── main.py            # 程序入口
```

## 🚀 快速开始

### 1. 环境要求
- Python 3.9+
- pip

### 2. 安装

```bash
# 克隆或下载项目
cd /Users/lucas/telegram-customer-bot

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件（已配置你的信息）：
- `BOT_TOKEN`: 你的机器人 Token
- `ADMIN_ID`: 你的 Telegram ID (7363537082)
- 其他配置根据需要调整

### 4. 运行

```bash
python main.py
```

## 📝 使用指南

### 客户端命令
- `/start` - 开始使用机器人
- `/help` - 获取帮助信息
- `/status` - 查看服务状态
- `/contact` - 联系人工客服

### 管理员命令
- `/stats` - 查看统计信息
- `/sessions` - 查看活跃会话
- `/reply <用户ID> <消息>` - 回复指定用户
- `/broadcast <消息>` - 广播消息
- `/settings` - 机器人设置

### 回复客户消息
1. **直接回复**：回复机器人转发的消息
2. **命令回复**：使用 `/reply` 命令
3. **快捷按钮**：使用消息下方的快捷操作按钮

## 🔧 高级配置

### 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `BOT_TOKEN` | Telegram Bot Token | 必填 |
| `ADMIN_ID` | 管理员 Telegram ID | 必填 |
| `LOG_LEVEL` | 日志级别 | INFO |
| `DATABASE_TYPE` | 数据库类型 | sqlite |
| `BUSINESS_HOURS_START` | 营业开始时间 | 09:00 |
| `BUSINESS_HOURS_END` | 营业结束时间 | 18:00 |
| `TIMEZONE` | 时区 | Asia/Shanghai |

### 功能开关

在 `.env` 文件中可以控制功能开关：

- `ENABLE_AUTO_REPLY` - 自动回复
- `ENABLE_STATISTICS` - 统计功能
- `ENABLE_CUSTOMER_HISTORY` - 客户历史记录

## 🛡️ 安全特性

- ✅ **权限控制**：严格的管理员权限验证
- ✅ **速率限制**：防止消息轰炸
- ✅ **错误处理**：完善的异常捕获和处理
- ✅ **日志记录**：详细的操作日志
- ✅ **数据加密**：敏感数据加密存储（可选）

## 📊 监控和维护

### 日志文件
- 位置：`logs/bot.log`
- JSON 格式：`logs/bot.json`
- 自动轮转：达到 10MB 自动轮转

### 数据库维护
- 自动清理：30天以上的已关闭会话
- 备份建议：定期备份 `data/bot.db`

### 性能优化
- 异步处理：所有 I/O 操作异步执行
- 连接池：数据库连接池管理
- 缓存：频繁访问数据缓存

## 🔄 更新和升级

```bash
# 备份数据
cp -r data data_backup

# 更新代码
git pull  # 如果使用git

# 更新依赖
pip install -r requirements.txt --upgrade

# 重启机器人
python main.py
```

## 🐛 故障排除

### 常见问题

1. **机器人无响应**
   - 检查 Token 是否正确
   - 检查网络连接
   - 查看日志文件

2. **消息未转发**
   - 确认管理员 ID 正确
   - 检查机器人权限

3. **数据库错误**
   - 检查 data 目录权限
   - 尝试删除并重建数据库

### 调试模式

在 `.env` 中设置 `DEBUG=true` 启用调试模式。

## 📈 扩展开发

### 添加新功能模块

1. 在 `src/modules/` 创建新模块
2. 继承 `BaseHandler` 类
3. 在 `bot.py` 中注册处理器

### 自定义中间件

```python
from src.core.router import MessageRouter

router = MessageRouter(config)

@router.middleware()
async def custom_middleware(context, telegram_context):
    # 处理逻辑
    return True  # 继续处理
```

## 🤝 技术支持

- 查看日志：`tail -f logs/bot.log`
- 数据库查询：使用 SQLite 工具打开 `data/bot.db`
- 性能监控：查看 `/stats` 命令输出

## 📄 许可证

MIT License

## 🙏 致谢

- python-telegram-bot - Telegram Bot API 库
- SQLite - 轻量级数据库
- 所有开源贡献者

---

**当前版本**: 1.0.0
**最后更新**: 2025-09-24
**作者**: 阿泰 (@xiaobai_80)