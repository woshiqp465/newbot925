#\!/bin/bash

cd /home/atai/telegram-bot

# 加载.env文件中的环境变量
export $(grep -v "^#" .env | grep -v "^$" | xargs)

# 设置代理
export ALL_PROXY=socks5://127.0.0.1:1080

echo "=== 环境变量检查 ==="
echo "ANTHROPIC_AUTH_TOKEN: ${ANTHROPIC_AUTH_TOKEN:0:30}..."
echo "ANTHROPIC_BASE_URL: $ANTHROPIC_BASE_URL"
echo "BOT_TOKEN: ${BOT_TOKEN:0:30}..."
echo "========================"

# 启动bot
screen -dmS agent_bot bash -c "python3 -u integrated_bot_ai.py 2>&1 | tee bot_agent_sdk.log"

echo "Bot已在screen会话中启动"
echo "使用 screen -r agent_bot 查看日志"
