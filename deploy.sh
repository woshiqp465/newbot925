#!/bin/bash

# ========================================
# Telegram Bot 部署脚本
# 用于在虚拟机上自动部署和运行机器人
# ========================================

echo "========================================="
echo "开始部署 Telegram 整合机器人"
echo "========================================="

# 1. 更新系统包
echo "📦 更新系统包..."
sudo apt-get update -y
sudo apt-get upgrade -y

# 2. 安装必要的软件
echo "🔧 安装必要软件..."
sudo apt-get install -y python3 python3-pip git screen

# 3. 克隆项目
echo "📥 克隆项目..."
if [ -d "newbot925" ]; then
    echo "项目已存在，更新代码..."
    cd newbot925
    git pull
else
    git clone https://github.com/woshiqp465/newbot925.git
    cd newbot925
fi

# 4. 安装Python依赖
echo "📚 安装Python依赖..."
pip3 install -r requirements.txt

# 5. 创建.env文件（如果不存在）
if [ ! -f .env ]; then
    echo "⚙️ 创建配置文件..."
    cp .env.example .env
    echo ""
    echo "⚠️ 请编辑 .env 文件并填写你的配置："
    echo "   nano .env"
    echo ""
    echo "需要配置："
    echo "- BOT_TOKEN=你的机器人token"
    echo "- ADMIN_ID=你的Telegram ID"
    echo ""
fi

# 6. 创建启动脚本
echo "📝 创建启动脚本..."
cat > start_bot.sh << 'EOF'
#!/bin/bash
# 检查是否已有session在运行
if screen -list | grep -q "telegram_bot"; then
    echo "❌ 机器人已在运行！"
    echo "使用 'screen -r telegram_bot' 查看"
    echo "使用 './stop_bot.sh' 停止"
    exit 1
fi

# 在screen会话中启动机器人
echo "🚀 启动机器人..."
screen -dmS telegram_bot python3 integrated_bot.py
echo "✅ 机器人已在后台启动！"
echo ""
echo "使用以下命令管理："
echo "- 查看日志: screen -r telegram_bot"
echo "- 退出查看: Ctrl+A 然后按 D"
echo "- 停止机器人: ./stop_bot.sh"
EOF

# 7. 创建停止脚本
cat > stop_bot.sh << 'EOF'
#!/bin/bash
# 停止机器人
if screen -list | grep -q "telegram_bot"; then
    screen -X -S telegram_bot quit
    echo "✅ 机器人已停止"
else
    echo "❌ 机器人未在运行"
fi
EOF

# 8. 创建查看日志脚本
cat > logs.sh << 'EOF'
#!/bin/bash
# 查看机器人日志
if screen -list | grep -q "telegram_bot"; then
    screen -r telegram_bot
else
    echo "❌ 机器人未在运行"
    echo "使用 './start_bot.sh' 启动"
fi
EOF

# 9. 创建自动重启脚本（防止意外停止）
cat > monitor_bot.sh << 'EOF'
#!/bin/bash
# 监控并自动重启机器人
while true; do
    if ! screen -list | grep -q "telegram_bot"; then
        echo "[$(date)] 机器人已停止，正在重启..."
        screen -dmS telegram_bot python3 integrated_bot.py
        echo "[$(date)] 机器人已重启"
    fi
    sleep 60  # 每60秒检查一次
done
EOF

# 10. 设置脚本权限
chmod +x start_bot.sh stop_bot.sh logs.sh monitor_bot.sh

# 11. 创建系统服务（可选，开机自启）
echo "📝 创建系统服务..."
sudo cat > /tmp/telegram-bot.service << EOF
[Unit]
Description=Telegram Integration Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
ExecStart=/usr/bin/python3 $PWD/integrated_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 询问是否安装为系统服务
echo ""
echo "是否将机器人安装为系统服务？(开机自动启动) [y/N]"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    sudo mv /tmp/telegram-bot.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable telegram-bot.service
    echo "✅ 系统服务已安装"
    echo ""
    echo "使用以下命令管理服务："
    echo "- 启动: sudo systemctl start telegram-bot"
    echo "- 停止: sudo systemctl stop telegram-bot"
    echo "- 状态: sudo systemctl status telegram-bot"
    echo "- 日志: sudo journalctl -u telegram-bot -f"
else
    rm /tmp/telegram-bot.service
fi

echo ""
echo "========================================="
echo "✅ 部署完成！"
echo "========================================="
echo ""
echo "📋 使用说明："
echo ""
echo "1. 首先配置环境变量："
echo "   nano .env"
echo ""
echo "2. 创建Pyrogram session："
echo "   python3 create_session.py"
echo ""
echo "3. 启动机器人："
echo "   ./start_bot.sh"
echo ""
echo "4. 查看运行状态："
echo "   ./logs.sh"
echo ""
echo "5. 停止机器人："
echo "   ./stop_bot.sh"
echo ""
echo "6. 自动监控（推荐）："
echo "   screen -dmS monitor ./monitor_bot.sh"
echo ""
echo "========================================="