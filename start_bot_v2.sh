#!/bin/bash
source ~/.bashrc

# 显示环境变量
echo "=== 环境变量检查 ==="
echo "ANTHROPIC_AUTH_TOKEN: ${ANTHROPIC_AUTH_TOKEN:0:30}..."
echo "ANTHROPIC_BASE_URL: $ANTHROPIC_BASE_URL"
echo ""

# 清理Python缓存
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
find . -name '*.pyc' -delete 2>/dev/null

# 设置代理
export ALL_PROXY=socks5://127.0.0.1:1080

# 启动Bot
python3 -u integrated_bot_ai.py 2>&1 | tee bot_running.log
