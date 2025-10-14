#!/bin/bash
set -euo pipefail

LOG_FILE="$HOME/daily_self_check.log"

exec >>"$LOG_FILE" 2>&1

now() {
    date "+%Y-%m-%d %H:%M:%S %Z"
}

echo ""
echo "=== $(now) 自检开始 ==="

check_service() {
    local service="$1"
    if systemctl is-active --quiet "$service"; then
        echo "[$(now)] ✅ 服务 $service 运行正常"
    else
        echo "[$(now)] ⚠️ 服务 $service 未运行，尝试重启"
        if sudo systemctl restart "$service"; then
            sleep 3
            if systemctl is-active --quiet "$service"; then
                echo "[$(now)] ✅ 服务 $service 重启成功"
            else
                echo "[$(now)] ❌ 服务 $service 重启失败，请手动检查"
            fi
        else
            echo "[$(now)] ❌ 无法执行重启命令 $service"
        fi
    fi
}

# 确保核心服务在线
check_service "v2ray.service"
check_service "proxy-monitor.service"
check_service "system-monitor.service"

# 检查并恢复 Telegram Bot
if screen -list | grep -q "\.agent_bot"; then
    echo "[$(now)] ✅ Telegram Bot 已在 screen 会话中运行"
else
    echo "[$(now)] ⚠️ Telegram Bot 未运行，尝试启动"
    if /home/atai/telegram-bot/manage_bot.sh start; then
        echo "[$(now)] ✅ Telegram Bot 启动命令已执行"
    else
        echo "[$(now)] ❌ Telegram Bot 启动失败，请检查"
    fi
fi

# 输出状态报告
/home/atai/check_status.sh || echo "[$(now)] ⚠️ 执行 check_status.sh 失败"

echo "=== $(now) 自检结束 ==="
