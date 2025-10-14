#!/bin/bash

# 直接设置环境变量（不依赖bashrc）
export ANTHROPIC_AUTH_TOKEN='cr_6054f2a49ea9e2e848b955cc65be8648df80c6476c9f3cf1164628ac5fb4f896'
export ANTHROPIC_BASE_URL='http://202.79.167.23:3000/api/'
export ALL_PROXY='socks5://127.0.0.1:1080'

echo "=== 环境变量已设置 ==="
echo "ANTHROPIC_AUTH_TOKEN: ${ANTHROPIC_AUTH_TOKEN:0:30}..."
echo "ANTHROPIC_BASE_URL: $ANTHROPIC_BASE_URL"
echo "ALL_PROXY: $ALL_PROXY"
echo ""

# 清理缓存
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
find . -name '*.pyc' -delete 2>/dev/null

# 启动Bot
python3 -u integrated_bot_ai.py 2>&1 | tee bot_running.log
