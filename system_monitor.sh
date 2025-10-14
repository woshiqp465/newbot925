#!/bin/bash

# 系统监控脚本 - 确保所有代理服务正常运行
LOG_FILE="/home/atai/system_monitor.log"

timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

log_message() {
    echo "[$(timestamp)] $1" >> "$LOG_FILE"
}

is_port_listening() {
    local port="1080"
    if command -v ss >/dev/null 2>&1; then
        ss -tuln 2>/dev/null | grep -q ":${port} "
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln 2>/dev/null | grep -q ":${port}"
    else
        nc -z 127.0.0.1 "${port}" >/dev/null 2>&1
    fi
}

restart_service_if_needed() {
    local service="$1"
    if systemctl is-enabled --quiet "$service" 2>/dev/null || systemctl is-active --quiet "$service" 2>/dev/null; then
        log_message "INFO: Attempting to restart ${service}"
        sudo systemctl restart "$service" 2>/dev/null
        sleep 5
        if is_port_listening; then
            log_message "SUCCESS: ${service} is providing proxy access"
            return 0
        fi
    fi
    return 1
}

check_proxy_stack() {
    if is_port_listening; then
        log_message "INFO: Proxy port 1080 is listening"
        return 0
    fi

    log_message "WARNING: Proxy port 1080 not listening, attempting recovery"

    # 仅尝试重启 V2Ray
    if restart_service_if_needed "v2ray.service"; then
        return 0
    fi

    log_message "ERROR: Unable to restore proxy listening state"
    return 1
}

check_proxy_connection() {
    if curl --socks5 127.0.0.1:1080 -s -m 5 http://ifconfig.me >/dev/null 2>&1; then
        log_message "INFO: Proxy connection is working"
        return 0
    else
        log_message "WARNING: Proxy connection failed, trying to recover"
        restart_service_if_needed "v2ray.service"
        sleep 5
        if curl --socks5 127.0.0.1:1080 -s -m 5 http://ifconfig.me >/dev/null 2>&1; then
            log_message "SUCCESS: Proxy connection restored"
            return 0
        fi
        log_message "ERROR: Proxy connection still failing after recovery attempts"
        return 1
    fi
}

check_monitor_service() {
    if pgrep -f "auto_proxy_check.sh" >/dev/null 2>&1; then
        log_message "INFO: Auto monitor script is running"
    else
        log_message "WARNING: Auto monitor script not running, starting service"
        sudo systemctl start proxy-monitor.service 2>/dev/null
    fi
}

main_loop() {
    log_message "=== System Monitor Started ==="
    while true; do
        check_proxy_stack
        check_proxy_connection
        check_monitor_service
        sleep 300
    done
}

if [ "$1" = "--daemon" ]; then
    main_loop
else
    log_message "=== Single Check ==="
    check_proxy_stack
    check_proxy_connection
    check_monitor_service
    echo "Check complete. See $LOG_FILE for details"
fi
