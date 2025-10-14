#!/bin/bash
source ~/.bashrc
export ALL_PROXY=socks5://127.0.0.1:1080
export ANTHROPIC_API_KEY="$ANTHROPIC_AUTH_TOKEN"

echo "环境变量检查:"
echo "ANTHROPIC_AUTH_TOKEN: ${ANTHROPIC_AUTH_TOKEN:0:20}..."
echo "ANTHROPIC_BASE_URL: $ANTHROPIC_BASE_URL"
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:20}..."
echo "ALL_PROXY: $ALL_PROXY"
echo ""

python3 integrated_bot_ai.py 2>&1 | tee bot_running.log
