#!/bin/bash
echo "======================================"
echo "虚拟机 Bot 完整状态检查"
echo "======================================"
echo

echo "1. Bot进程状态:"
/home/atai/telegram-bot/manage_bot.sh status | grep -E "运行中|Detached|未找到"
echo

echo "2. Screen会话:"
screen -ls | grep agent_bot
echo

echo "3. 最新活动 (最近5条):"
tail -5 /home/atai/telegram-bot/bot_agent_sdk.log | grep -E "INFO|ERROR" | tail -3
echo

echo "4. 数据库记录数:"
python3 << 'PYEOF'
import sqlite3
conn = sqlite3.connect('/home/atai/bot_data/cache.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM search_cache')
total = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(DISTINCT command || keyword) FROM search_cache')
unique = cursor.fetchone()[0]
print(f"总记录: {total}, 唯一搜索: {unique}")
conn.close()
PYEOF
echo

echo "5. 环境变量配置:"
echo "ANTHROPIC_AUTH_TOKEN: ${ANTHROPIC_AUTH_TOKEN:0:20}..."
echo "ANTHROPIC_BASE_URL: $ANTHROPIC_BASE_URL"
echo

echo "======================================"
echo "✅ 检查完成"
echo "======================================"
