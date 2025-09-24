#!/bin/bash

echo "📡 监控 Telegram 机器人..."
echo "================================"
echo "按 Ctrl+C 退出"
echo ""

tail -f bot.out | grep -E "(from user|forward|reply|消息|客户|管理员|ERROR|WARNING)"