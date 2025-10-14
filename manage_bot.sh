#!/bin/bash
# Telegram Bot 管理脚本
# 统一管理 integrated_bot_ai.py (使用 claude-agent-sdk)

BOT_DIR="/home/atai/telegram-bot"
BOT_SCRIPT="integrated_bot_ai.py"
SCREEN_NAME="agent_bot"
LOG_FILE="bot_agent_sdk.log"

# 环境变量
export ANTHROPIC_BASE_URL="http://202.79.167.23:3000/api"
export ANTHROPIC_AUTH_TOKEN="cr_9792f20a98f055e204248a41f280780ca2fb8f08f35e60c785e5245653937e06"
export ALL_PROXY="socks5://127.0.0.1:1080"

cd "$BOT_DIR" || exit 1

case "$1" in
    start)
        echo "🚀 启动 Telegram Bot..."
        if screen -list | grep -q "$SCREEN_NAME"; then
            echo "⚠️  Bot 已经在运行中"
            screen -ls | grep "$SCREEN_NAME"
        else
            screen -dmS "$SCREEN_NAME" bash -c "cd $BOT_DIR && python3 -u $BOT_SCRIPT 2>&1 | tee $LOG_FILE"
            sleep 2
            if screen -list | grep -q "$SCREEN_NAME"; then
                echo "✅ Bot 已启动"
                screen -ls | grep "$SCREEN_NAME"
                echo ""
                echo "📝 查看日志: tail -f $BOT_DIR/$LOG_FILE"
            else
                echo "❌ 启动失败，请检查日志"
            fi
        fi
        ;;
    
    stop)
        echo "🛑 停止 Telegram Bot..."
        if screen -list | grep -q "$SCREEN_NAME"; then
            screen -S "$SCREEN_NAME" -X quit
            sleep 1
            echo "✅ Bot 已停止"
        else
            echo "⚠️  Bot 没有运行"
        fi
        ;;
    
    restart)
        echo "🔄 重启 Telegram Bot..."
        $0 stop
        sleep 2
        $0 start
        ;;
    
    status)
        echo "📊 Bot 状态检查..."
        echo ""
        if screen -list | grep -q "$SCREEN_NAME"; then
            echo "✅ Bot 运行中"
            screen -ls | grep "$SCREEN_NAME"
            echo ""
            echo "最近日志:"
            tail -20 "$BOT_DIR/$LOG_FILE"
        else
            echo "❌ Bot 未运行"
        fi
        ;;
    
    logs)
        echo "📝 实时日志 (Ctrl+C 退出)..."
        tail -f "$BOT_DIR/$LOG_FILE"
        ;;
    
    attach)
        echo "🔗 进入 Bot Screen 会话 (Ctrl+A, D 退出)..."
        screen -r "$SCREEN_NAME"
        ;;
    
    info)
        echo "ℹ️  Bot 信息"
        echo "============================================"
        echo "脚本: $BOT_SCRIPT"
        echo "位置: $BOT_DIR"
        echo "日志: $LOG_FILE"
        echo "Screen: $SCREEN_NAME"
        echo "使用: claude-agent-sdk (Python)"
        echo "模型: claude-sonnet-4-5-20250929"
        echo ""
        echo "功能:"
        echo "  - AI对话引导 (claude-agent-sdk)"
        echo "  - Pyrogram搜索 (镜像@openaiw_bot)"
        echo "  - 自动翻页缓存 (SQLite 30天)"
        echo "  - 智能按钮生成"
        echo "============================================"
        ;;
    
    *)
        echo "Telegram Bot 管理脚本"
        echo ""
        echo "用法: $0 {start|stop|restart|status|logs|attach|info}"
        echo ""
        echo "命令说明:"
        echo "  start    - 启动 Bot"
        echo "  stop     - 停止 Bot"
        echo "  restart  - 重启 Bot"
        echo "  status   - 查看运行状态"
        echo "  logs     - 实时查看日志"
        echo "  attach   - 进入 Screen 会话"
        echo "  info     - 显示 Bot 信息"
        exit 1
        ;;
esac
