#!/bin/bash

echo "========================================"
echo "        系统状态检查报告"
echo "        $(date)"
echo "========================================"
echo ""

# 服务状态
echo "【系统服务状态】"
echo -n "  V2Ray: "
systemctl is-active v2ray.service
echo -n "  代理监控: "
systemctl is-active proxy-monitor.service
echo -n "  系统监控: "
systemctl is-active system-monitor.service
echo ""

# 进程状态
echo "【进程运行状态】"
if pgrep -x "v2ray" > /dev/null; then
    echo "  ✓ V2Ray 进程正在运行"
else
    echo "  ✗ V2Ray 进程未运行"
fi

if pgrep -f "auto_proxy_check.sh" > /dev/null; then
    echo "  ✓ 自动检测脚本正在运行"
else
    echo "  ✗ 自动检测脚本未运行"
fi

if pgrep -f "system_monitor.sh" > /dev/null; then
    echo "  ✓ 系统监控脚本正在运行"
else
    echo "  ✗ 系统监控脚本未运行"
fi
echo ""

# 网络连接
echo "【网络连接状态】"
echo -n "  代理端口 (1080): "
if ss -tuln | grep -q ":1080"; then
    echo "监听中"
else
    echo "未监听"
fi

echo -n "  外部IP: "
timeout 3 curl --socks5 127.0.0.1:1080 -s http://ifconfig.me || echo "无法连接"
echo ""

# 自启动配置
echo ""
echo "【开机自启动配置】"
for service in v2ray proxy-monitor system-monitor; do
    if systemctl is-enabled $service.service &>/dev/null; then
        echo "  ✓ $service 已设置开机自启"
    else
        echo "  ✗ $service 未设置开机自启"
    fi
done

echo ""
echo "【最近的日志】"
tail -5 ~/system_monitor.log 2>/dev/null || echo "  暂无日志"
echo ""
echo "========================================"
