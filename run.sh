#!/bin/bash

# 客服机器人启动脚本

echo "🤖 Starting Telegram Customer Service Bot..."
echo "================================"

# 进入项目目录
cd /Users/lucas/telegram-customer-bot

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed"
    exit 1
fi

# 检查环境文件
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# 创建必要的目录
mkdir -p logs data

# 启动机器人
echo "📡 Connecting to Telegram..."
python3 main.py

echo "✅ Bot stopped"