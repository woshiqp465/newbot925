#!/bin/bash
# 启动整合版机器人脚本

# 设置代理
export ALL_PROXY=socks5://127.0.0.1:1080
export export HTTP_PROXY=socks5://127.0.0.1:1080

echo "🔄 停止现有机器人进程..."
pkill -f "python3.*bot" 2>/dev/null
sleep 2

echo "✅ 代理已配置: 127.0.0.1:8118"
echo "🚀 启动整合版机器人..."

# 使用screen启动
screen -dmS telegram_bot python3 integrated_bot.py

echo "✅ 机器人已在后台启动！"
echo ""
echo "使用以下命令管理："
echo "- 查看日志: screen -r telegram_bot"
echo "- 退出查看: Ctrl+A 然后按 D"
echo "- 停止机器人: screen -X -S telegram_bot quit"