#!/bin/bash
echo "==========================================="
echo "🔍 自动翻页功能检查"
echo "==========================================="
echo ""

echo "📂 1. 数据库状态"
echo "-------------------------------------------"
if [ -f cache.db ]; then
    DB_SIZE=$(du -h cache.db | cut -f1)
    echo "✅ 数据库存在: cache.db ($DB_SIZE)"
    
    # 检查表结构
    echo ""
    echo "表结构:"
    sqlite3 cache.db '.schema search_cache' 2>/dev/null || echo "⚠️  无法读取表结构"
    
    # 统计记录
    echo ""
    TOTAL_RECORDS=$(sqlite3 cache.db 'SELECT COUNT(*) FROM search_cache;' 2>/dev/null)
    echo "总记录数: $TOTAL_RECORDS"
    
    if [ "$TOTAL_RECORDS" -gt 0 ]; then
        echo ""
        echo "📊 缓存统计 (按搜索分组):"
        sqlite3 cache.db 'SELECT command, keyword, COUNT(*) as pages, MAX(page) as max_page FROM search_cache GROUP BY command, keyword;' 2>/dev/null
    else
        echo "⚠️  数据库为空，还没有搜索记录"
    fi
else
    echo "❌ 数据库不存在"
fi

echo ""
echo "📝 2. 日志中的翻页记录"
echo "-------------------------------------------"
PAGINATION_LOGS=$(grep -c '\[翻页\]' bot_agent_sdk.log 2>/dev/null)
if [ "$PAGINATION_LOGS" -gt 0 ]; then
    echo "✅ 找到 $PAGINATION_LOGS 条翻页日志"
    echo ""
    echo "最近的翻页活动:"
    grep '\[翻页\]' bot_agent_sdk.log 2>/dev/null | tail -10
else
    echo "⚠️  还没有翻页活动记录"
fi

echo ""
echo "🔧 3. 代码检查"
echo "-------------------------------------------"
if grep -q 'class AutoPaginationManager' integrated_bot_ai.py; then
    echo "✅ AutoPaginationManager 类存在"
fi
if grep -q 'async def _paginate' integrated_bot_ai.py; then
    echo "✅ _paginate 方法存在"
fi
if grep -q 'start_pagination' integrated_bot_ai.py; then
    echo "✅ start_pagination 方法存在"
fi
if grep -q '_has_next' integrated_bot_ai.py; then
    echo "✅ _has_next 按钮检测方法存在"
fi
if grep -q '_click_next' integrated_bot_ai.py; then
    echo "✅ _click_next 点击方法存在"
fi

echo ""
echo "==========================================="
echo "📝 总结"
echo "==========================================="

if [ "$TOTAL_RECORDS" -gt 0 ]; then
    echo "✅ 翻页功能正常，已保存 $TOTAL_RECORDS 条记录"
elif [ "$PAGINATION_LOGS" -gt 0 ]; then
    echo "⚠️  翻页功能运行过，但数据库可能已清空"
else
    echo "ℹ️  翻页功能已配置，等待用户触发搜索"
fi

echo ""
echo "💡 触发方法:"
echo "  1. 向 @ktfund_bot 发送消息"
echo "  2. 点击AI回复的搜索按钮"
echo "  3. 或直接发送 /search 关键词"
echo "==========================================="
