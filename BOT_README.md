# Telegram Bot 管理指南

## 📌 概述

**唯一运行的脚本**: `integrated_bot_ai.py`

这是一个**统一的、完整集成的** Telegram bot，包含所有功能：
- ✅ AI 对话引导（使用 claude-agent-sdk）
- ✅ Pyrogram 搜索（镜像 @openaiw_bot）
- ✅ 自动翻页缓存（SQLite 30天）
- ✅ 智能按钮生成

## 🚀 快速使用

### 使用管理脚本（推荐）

```bash
# SSH 到虚拟机
ssh atai@192.168.9.159

# 查看所有命令
/home/atai/telegram-bot/manage_bot.sh

# 常用命令
/home/atai/telegram-bot/manage_bot.sh status   # 查看状态
/home/atai/telegram-bot/manage_bot.sh start    # 启动 bot
/home/atai/telegram-bot/manage_bot.sh stop     # 停止 bot
/home/atai/telegram-bot/manage_bot.sh restart  # 重启 bot
/home/atai/telegram-bot/manage_bot.sh logs     # 查看日志
/home/atai/telegram-bot/manage_bot.sh info     # 显示信息
```

### 手动操作

```bash
# 启动
cd /home/atai/telegram-bot
export ANTHROPIC_BASE_URL="http://202.79.167.23:3000/api"
export ANTHROPIC_AUTH_TOKEN="cr_9792f20a98f055e204248a41f280780ca2fb8f08f35e60c785e5245653937e06"
export ALL_PROXY="socks5://127.0.0.1:1080"
screen -dmS agent_bot bash -c 'python3 -u integrated_bot_ai.py 2>&1 | tee bot_agent_sdk.log'

# 查看运行状态
screen -ls

# 查看日志
tail -f bot_agent_sdk.log

# 进入 screen 会话
screen -r agent_bot
# 退出 screen: Ctrl+A, D

# 停止
screen -S agent_bot -X quit
```

## 📁 文件说明

### 🟢 当前使用的文件

| 文件 | 说明 |
|------|------|
| `integrated_bot_ai.py` | **主bot脚本**（唯一运行） |
| `claude_agent_wrapper.py` | Claude Agent SDK 包装器 |
| `manage_bot.sh` | Bot 管理脚本 |
| `bot_agent_sdk.log` | 运行日志 |
| `cache.db` | SQLite 缓存数据库 |
| `user_session.session` | Pyrogram 会话文件 |

### 🟡 备份文件（不使用）

| 文件 | 说明 |
|------|------|
| `integrated_bot_ai_backup_*.py` | 自动备份 |
| `integrated_bot_ai.backup.py` | 手动备份 |

### 🔴 旧版文件（可删除）

| 文件 | 说明 |
|------|------|
| `agent_bot.py` | 旧版 Agent Bot |
| `unified_telegram_bot.py` | 旧版统一 Bot |
| `integrated_bot.py` | 旧版集成 Bot |
| `bot_without_mirror.py` | 旧版无镜像 Bot |

## 🔧 配置信息

### 环境变量

已配置在 `~/.bashrc`:
```bash
export ANTHROPIC_BASE_URL="http://202.79.167.23:3000/api"
export ANTHROPIC_AUTH_TOKEN="cr_9792f20a98f055e204248a41f280780ca2fb8f08f35e60c785e5245653937e06"
```

### Bot 信息

- **Bot名称**: @ktfund_bot
- **使用SDK**: claude-agent-sdk (Python)
- **AI模型**: claude-sonnet-4-5-20250929
- **镜像Bot**: @openaiw_bot
- **代理**: socks5://127.0.0.1:1080

## 🔍 监控与调试

### 实时监控日志

```bash
# 监控所有日志
tail -f /home/atai/telegram-bot/bot_agent_sdk.log

# 监控 AI 调用
tail -f /home/atai/telegram-bot/bot_agent_sdk.log | grep -E 'Claude|Agent|AI'

# 监控用户消息
tail -f /home/atai/telegram-bot/bot_agent_sdk.log | grep -E '用户|消息|搜索'

# 监控错误
tail -f /home/atai/telegram-bot/bot_agent_sdk.log | grep -E 'ERROR|❌|失败'
```

### 检查运行状态

```bash
# 检查 screen 会话
screen -ls

# 检查进程
ps aux | grep integrated_bot_ai.py

# 检查日志最新内容
tail -50 /home/atai/telegram-bot/bot_agent_sdk.log
```

## 🐛 常见问题

### Bot 无响应

1. 检查是否运行：`/home/atai/telegram-bot/manage_bot.sh status`
2. 查看日志错误：`tail -100 /home/atai/telegram-bot/bot_agent_sdk.log | grep ERROR`
3. 重启 bot：`/home/atai/telegram-bot/manage_bot.sh restart`

### AI 调用失败

检查环境变量：
```bash
echo $ANTHROPIC_BASE_URL
echo $ANTHROPIC_AUTH_TOKEN
```

如果为空，运行：
```bash
source ~/.bashrc
```

### Pyrogram 搜索失败

1. 检查代理：`curl --socks5 127.0.0.1:1080 https://api.telegram.org`
2. 检查会话文件：`ls -l user_session.session`

## 📊 系统架构

```
Telegram 用户
    ↓
@ktfund_bot (虚拟机)
    ↓
integrated_bot_ai.py
    ├─ Claude Agent SDK → AI 对话
    ├─ Pyrogram → 搜索 @openaiw_bot
    ├─ SQLite → 缓存管理
    └─ Auto Pagination → 后台翻页
```

## ⚙️ 维护建议

### 定期检查

- 每天检查 bot 状态：`/home/atai/telegram-bot/manage_bot.sh status`
- 每周清理旧日志：保留最近30天
- 每月备份数据库：`cache.db`

### 日志管理

```bash
# 查看日志大小
du -h /home/atai/telegram-bot/bot_agent_sdk.log

# 如果日志太大，可以轮转
cd /home/atai/telegram-bot
mv bot_agent_sdk.log bot_agent_sdk.log.old
/home/atai/telegram-bot/manage_bot.sh restart
```

## 🎯 性能优化

当前配置已优化：
- ✅ 使用 SQLite 缓存（30天）
- ✅ 自动翻页（后台异步）
- ✅ 对话历史管理（最近5轮）
- ✅ 智能按钮去重

## 📝 更新日志

### 2025-10-07
- ✅ 完成 claude-agent-sdk 集成
- ✅ 创建统一管理脚本
- ✅ 虚拟机完全独立运行
- ✅ 不再依赖 Mac 服务

---

**注意**：其他所有旧 bot 脚本都已弃用，只需运行 `integrated_bot_ai.py`！
