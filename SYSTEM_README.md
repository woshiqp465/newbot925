# 系统完整部署文档

## 系统概述

这是一个完整的 **V2Ray代理 + Telegram AI客服机器人** 自动化系统。

### 主要组件

1. **V2Ray代理服务** - 提供SOCKS5代理（端口1080）
2. **自动监控系统** - 确保代理服务24/7运行
3. **Telegram AI客服机器人** - 集成Claude AI的智能客服

## 目录结构

### Telegram Bot 代码
- `integrated_bot_ai.py` - 主Bot脚本（唯一运行）
- `claude_agent_wrapper.py` - Claude AI SDK包装器
- `database.py` - SQLite缓存管理
- `manage_bot.sh` - Bot管理脚本
- `BOT_README.md` - Bot详细文档

### 监控脚本
- `auto_proxy_check.sh` - 代理自动检测和修复（1分钟循环）
- `system_monitor.sh` - 系统监控（5分钟循环）
- `check_status.sh` - 系统状态检查报告
- `daily_self_check.sh` - 每日自检脚本

### 配置文件
- `.env.example` - 环境变量示例（需要复制为.env并填写）
- `requirements.txt` - Python依赖

## 快速部署

### 1. 安装依赖

```bash
# 安装Python依赖
pip3 install -r requirements.txt

# 安装V2Ray（如果没有）
bash <(curl -L https://raw.githubusercontent.com/v2fly/fhs-install-v2ray/master/install-release.sh)
```

### 2. 配置环境变量

```bash
# 复制并编辑环境变量
cp .env.example .env
nano .env
```

必需的环境变量：
- `ANTHROPIC_BASE_URL` - Claude API地址
- `ANTHROPIC_AUTH_TOKEN` - Claude API Token
- `ALL_PROXY` - SOCKS5代理地址

### 3. 配置V2Ray

编辑 `/etc/v2ray/config.json`，配置您的V2Ray服务器信息。

### 4. 设置systemd服务

```bash
# 创建V2Ray服务（通常已有）
sudo systemctl enable v2ray
sudo systemctl start v2ray

# 创建代理监控服务
sudo tee /etc/systemd/system/proxy-monitor.service > /dev/null << 'SEOF'
[Unit]
Description=Proxy Auto Monitor and Repair Service
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
ExecStart=/bin/bash /home/YOUR_USERNAME/auto_proxy_check.sh --loop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SEOF

# 创建系统监控服务
sudo tee /etc/systemd/system/system-monitor.service > /dev/null << 'SEOF'
[Unit]
Description=System Monitor for Proxy Services
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
ExecStart=/bin/bash /home/YOUR_USERNAME/system_monitor.sh --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SEOF

# 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable proxy-monitor system-monitor
sudo systemctl start proxy-monitor system-monitor
```

### 5. 设置定时任务

```bash
crontab -e
```

添加：
```
# 开机启动
@reboot sleep 30 && sudo systemctl start v2ray proxy-monitor system-monitor

# 每天早上8点自检
TZ=Asia/Shanghai
0 8 * * * /home/YOUR_USERNAME/daily_self_check.sh
```

### 6. 创建Telegram会话

```bash
# 运行会话创建脚本
python3 create_session_manual.py
```

按照提示输入电话号码和验证码。

### 7. 启动Bot

```bash
# 使用管理脚本启动
./manage_bot.sh start

# 查看状态
./manage_bot.sh status

# 查看日志
./manage_bot.sh logs
```

## 配置说明

### Bot配置

在 `integrated_bot_ai.py` 中修改：

```python
API_ID = YOUR_API_ID
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "YOUR_BOT_TOKEN"
TARGET_BOT = "@openaiw_bot"  # 要镜像的目标bot
ADMIN_ID = YOUR_ADMIN_TELEGRAM_ID
```

### 代理配置

在 `auto_proxy_check.sh` 中修改服务器列表：

```bash
SERVERS=(
    "server1.example.com"
    "server2.example.com"
)
```

## 使用说明

### Bot命令

- `/start` - 启动Bot
- `/topchat` - 热门聊天搜索
- `/search <关键词>` - 搜索资源
- `/text <关键词>` - 文本搜索
- `/human <关键词>` - 人工搜索

### 管理命令

```bash
# Bot管理
./manage_bot.sh start     # 启动
./manage_bot.sh stop      # 停止
./manage_bot.sh restart   # 重启
./manage_bot.sh status    # 状态
./manage_bot.sh logs      # 查看日志

# 系统状态
./check_status.sh         # 完整状态报告

# 查看日志
tail -f bot_agent_sdk.log           # Bot日志
tail -f ~/proxy_monitor.log         # 代理监控日志
tail -f ~/system_monitor.log        # 系统监控日志
tail -f ~/daily_self_check.log      # 自检日志
```

## 架构说明

```
用户 → Telegram Bot
         ↓
  integrated_bot_ai.py
         ↓
    ├─ Claude AI (智能对话)
    ├─ Pyrogram (镜像搜索)
    └─ SQLite (缓存30天)
         ↓
    SOCKS5 Proxy (127.0.0.1:1080)
         ↓
      V2Ray
         ↓
      Internet
```

### 监控流程

```
system_monitor.sh (每5分钟)
    ↓
检查端口1080
    ↓ (失败)
重启v2ray
    ↓
记录日志

auto_proxy_check.sh (每1分钟)
    ↓
检查代理连接
    ↓ (失败)
切换服务器 & 重启
    ↓
记录日志

daily_self_check.sh (每天8点)
    ↓
检查所有服务
    ↓
重启失败的服务
    ↓
记录日志
```

## 故障排除

### Bot无响应

```bash
# 1. 检查Bot状态
./manage_bot.sh status

# 2. 查看日志
tail -50 bot_agent_sdk.log

# 3. 重启Bot
./manage_bot.sh restart
```

### 代理连接失败

```bash
# 1. 检查V2Ray状态
sudo systemctl status v2ray

# 2. 测试代理
curl --socks5 127.0.0.1:1080 https://www.google.com

# 3. 重启代理服务
sudo systemctl restart v2ray
```

### AI调用失败

```bash
# 检查环境变量
echo $ANTHROPIC_BASE_URL
echo $ANTHROPIC_AUTH_TOKEN

# 重新加载环境变量
source ~/.bashrc
```

## 日志位置

- Bot日志: `~/telegram-bot/bot_agent_sdk.log`
- 代理监控: `~/proxy_monitor.log`
- 系统监控: `~/system_monitor.log`
- 自检日志: `~/daily_self_check.log`

## 性能优化

- ✅ SQLite缓存（30天过期）
- ✅ 自动翻页（后台异步）
- ✅ 对话历史管理（最近5轮）
- ✅ 智能按钮去重

## 安全建议

1. 不要将 `.env` 文件提交到Git
2. 定期更改API密钥
3. 限制Bot管理员权限
4. 定期检查日志文件大小
5. 使用强密码保护服务器

## 维护建议

1. 每周检查日志文件大小
2. 每月清理旧日志
3. 定期备份 `cache.db`
4. 定期更新依赖包

## 技术栈

- **Python 3.8+**
- **Pyrogram** - Telegram用户端
- **python-telegram-bot** - Telegram Bot
- **Claude AI (Sonnet 4.5)** - AI对话
- **SQLite** - 缓存数据库
- **V2Ray** - 代理服务
- **systemd** - 服务管理

## 许可证

MIT License

## 作者

woshiqp465

## 更新日志

查看 `UPDATE_LOG_20251008.md` 了解详细更新记录。

---

**注意**: 本系统设计为7x24小时无人值守运行，所有服务都有自动监控和恢复机制。
