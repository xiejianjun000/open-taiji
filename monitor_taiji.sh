#!/bin/bash
# Taiji Agent 实时日志监控器
# 用法: ./monitor_taiji.sh

LOG_FILE="/Users/mac/.taiji/logs/taiji-agent.log"
LAST_LINE=""

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         实时监控 Taiji Agent 日志                            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "监控文件: $LOG_FILE"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "等待 taiji-agent 对话活动..."
echo ""

# 获取当前文件行数
LAST_LINE=$(wc -l < "$LOG_FILE")

while true; do
    CURRENT_LINE=$(wc -l < "$LOG_FILE")
    
    if [ "$CURRENT_LINE" -gt "$LAST_LINE" ]; then
        # 有新日志
        NEW_LINES=$((CURRENT_LINE - LAST_LINE))
        echo "--- $(date '+%H:%M:%S') --- 检测到 $NEW_LINES 条新日志 ---"
        tail -n "$NEW_LINES" "$LOG_FILE" | grep -E "(INFO|ERROR|WARNING|agent|chat|response)"
        echo ""
        LAST_LINE="$CURRENT_LINE"
    fi
    
    sleep 2
done
