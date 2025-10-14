#\!/bin/bash
cd /home/atai/telegram-bot

# 加载环境变量
export $(grep -v "^#" .env | grep -v "^$" | xargs)
export ALL_PROXY=socks5://127.0.0.1:1080

echo "=== Bot V3 启动 ==="
echo "ANTHROPIC_AUTH_TOKEN: ${ANTHROPIC_AUTH_TOKEN:0:30}..."
echo "BOT_TOKEN: ${BOT_TOKEN:0:30}..."
echo "==================="

# 启动V3
screen -dmS bot_v3 bash -c "python3 -u bot_v3.py 2>&1 | tee bot_v3.log"

echo "✅ Bot V3 已启动"
echo "查看日志: tail -f ~/telegram-bot/bot_v3.log"
echo "进入screen: screen -r bot_v3"
