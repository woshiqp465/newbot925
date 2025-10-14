#!/bin/bash
# 代理自动检测和修复脚本

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SERVERS=(
    "hk01.example.com"
    "hk02.example.com"
    "hk03.example.com"
    "hk04.example.com"
    "hk05.example.com"
    "hk06.example.com"
)

print_header() {
    echo "=========================================="
    echo "代理自动检测和修复脚本 v1.1"
    echo "=========================================="
}

is_proxy_process_running() {
    if pgrep -x "ss-local" >/dev/null 2>&1; then
        return 0
    fi
    if pgrep -x "v2ray" >/dev/null 2>&1; then
        return 0
    fi
    if command -v ss >/dev/null 2>&1; then
        ss -tuln 2>/dev/null | grep -q ':1080 '
        return $?
    fi
    return 1
}

check_proxy_process() {
    if is_proxy_process_running; then
        echo -e "${GREEN}✅ 代理进程/端口监听正常${NC}"
        return 0
    else
        echo -e "${RED}❌ 未检测到代理进程或端口监听${NC}"
        return 1
    fi
}

test_proxy_connection() {
    echo "测试代理连接..."
    if curl -s --socks5 127.0.0.1:1080 -m 5 https://www.google.com >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 代理连接正常${NC}"
        return 0
    else
        echo -e "${RED}❌ 代理连接失败${NC}"
        return 1
    fi
}

test_current_latency() {
    local server=$(grep '"server"' /etc/shadowsocks-libev/config.json 2>/dev/null | cut -d'"' -f4)
    if [ -z "$server" ]; then
        server=$(ss -tuln 2>/dev/null | awk '/:1080/ {print $5}' | head -n1)
    fi

    if [ -n "$server" ]; then
        echo "当前节点: $server"
        local avg_ping=$(ping -c 3 -W 1 "$server" 2>/dev/null | tail -1 | awk -F '/' '{print $5}')
        if [ -n "$avg_ping" ]; then
            echo -e "平均延迟: ${YELLOW}${avg_ping}ms${NC}"
        else
            echo -e "${YELLOW}⚠️  无法测试延迟${NC}"
        fi
    fi
}

check_ip_location() {
    echo "检查IP位置..."
    local city country
    city=$(curl -s --socks5 127.0.0.1:1080 -m 5 https://ipinfo.io/city 2>/dev/null || true)
    country=$(curl -s --socks5 127.0.0.1:1080 -m 5 https://ipinfo.io/country 2>/dev/null || true)

    if [[ "$country" =~ ^(HK|"HK"|香港)$ ]]; then
        echo -e "${GREEN}✅ 当前位置: ${city:-Unknown}, 香港${NC}"
        return 0
    fi

    if [[ "$country" == *"Rate limit"* ]]; then
        echo -e "${YELLOW}⚠️  IP 信息查询触发限流，稍后再试${NC}"
        return 2
    fi

    if [ -n "$country" ]; then
        echo -e "${YELLOW}⚠️  当前位置: ${city:-Unknown}, ${country}${NC}"
    else
        echo -e "${YELLOW}⚠️  无法获取位置信息${NC}"
    fi
    return 1
}

restart_proxy() {
    echo "尝试重启代理服务..."

    if systemctl is-active --quiet v2ray.service; then
        sudo systemctl restart v2ray.service
        sleep 3
        if is_proxy_process_running; then
            echo -e "${GREEN}✅ 已重启 v2ray 服务${NC}"
            return 0
        fi
    fi

    echo -e "${RED}❌ 未能恢复代理进程${NC}"
    return 1
}

select_best_node() {
    echo "测试预设节点延迟..."
    local best_server=""
    local best_ping=100000

    for server in "${SERVERS[@]}"; do
        local ping_time=$(ping -c 1 -W 1 "$server" 2>/dev/null | grep 'time=' | cut -d'=' -f4 | cut -d' ' -f1)
        if [ -n "$ping_time" ]; then
            echo "  $server: ${ping_time}ms"
            if command -v bc >/dev/null 2>&1; then
                if (( $(echo "$ping_time < $best_ping" | bc -l) )); then
                    best_ping=$ping_time
                    best_server=$server
                fi
            fi
        fi
    done

    if [ -n "$best_server" ]; then
        echo -e "${GREEN}最佳节点: $best_server (${best_ping}ms)${NC}"
    fi
}

summarize_status() {
    local process_status=$1
    local connection_status=$2
    local location_status=$3

    echo -e "\n${GREEN}=== 检测完成 ===${NC}"
    echo "状态摘要:"
    [ $process_status -eq 0 ] && echo "  ✅ 进程状态: 正常" || echo "  ❌ 进程状态: 异常"
    [ $connection_status -eq 0 ] && echo "  ✅ 连接状态: 正常" || echo "  ❌ 连接状态: 异常"
    case $location_status in
        0) echo "  ✅ 位置状态: 香港" ;;
        1) echo "  ⚠️  位置状态: 非香港" ;;
        2) echo "  ⚠️  位置状态: 查询限流" ;;
        *) echo "  ⚠️  位置状态: 暂无数据" ;;
    esac
}

main_cycle() {
    print_header
    echo -e "\n${YELLOW}=== 开始检测 ===${NC}"

    check_proxy_process
    local process_status=$?

    test_proxy_connection
    local connection_status=$?

    test_current_latency || true
    check_ip_location
    local location_status=$?

    if [ $process_status -ne 0 ] || [ $connection_status -ne 0 ]; then
        echo -e "\n${YELLOW}=== 开始自动修复 ===${NC}"
        if restart_proxy; then
            test_proxy_connection
            connection_status=$?
            check_proxy_process
            process_status=$?
        fi
    fi

    summarize_status $process_status $connection_status $location_status
}

if [ "${1:-}" = "--loop" ]; then
    while true; do
        main_cycle
        echo -e "\n等待60秒后再次检测..."
        sleep 60
    done
else
    main_cycle
fi
