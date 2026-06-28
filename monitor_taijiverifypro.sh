#!/bin/bash
# ════════════════════════════════════════════════════════
#  TaijiVerifyPro 实时监控器 v2.0
#  用法: ./monitor_taijiverifypro.sh
#  功能: 实时显示 taiji-agent 对话 + 防幻觉检测结果
# ════════════════════════════════════════════════════════

LOG_FILE="/Users/mac/.taiji/logs/taiji-agent.log"
FILTER_PATTERN="TaijiVerifyPro|taijiverifypro|BLOCK|WARNING|PASS|risk|verify|幻觉|拦截|判定"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     🛡️  TaijiVerifyPro v2.0 实时监控器                    ║"
echo "║     业界领先防幻觉系统 — 持续监控模式                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "📂 日志文件: $LOG_FILE"
echo "🎯 过滤模式: $FILTER_PATTERN"
echo "⏰ 启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  等待 taiji-agent 对话活动 (按 Ctrl+C 停止)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 检查日志文件是否存在
if [ ! -f "$LOG_FILE" ]; then
    echo "❌ 日志文件不存在: $LOG_FILE"
    echo "   请先启动 taiji-agent"
    exit 1
fi

# 获取当前行数作为起点
LAST_LINE=$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)
TOTAL_SHOWN=0

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

while true; do
    CURRENT_LINE=$(wc -l < "$LOG_FILE" 2>/dev/null || echo "$LAST_LINE")
    
    if [ "$CURRENT_LINE" -gt "$LAST_LINE" ]; then
        NEW_LINES=$((CURRENT_LINE - LAST_LINE))
        
        # 提取新日志并过滤
        NEW_CONTENT=$(tail -n "$NEW_LINES" "$LOG_FILE" 2>/dev/null)
        
        if [ -n "$NEW_CONTENT" ]; then
            # 显示时间戳和内容
            echo -e "\n${CYAN}$(date '+%H:%M:%S')${NC} | ${BOLD}检测到 ${NEW_LINES} 条新日志${NC}"
            echo "─$(printf '─%.0s' {1..64})"
            
            # 逐行处理，根据关键词着色
            while IFS= read -r line; do
                TIMESTAMP=$(echo "$line" | cut -d'|' -f1 | xargs)
                LEVEL=$(echo "$line" | cut -d'|' -f2 | xargs)
                MODULE=$(echo "$line" | cut -d'|' -f3 | xargs)
                MESSAGE=$(echo "$line" | cut -d'|' -f4- | sed 's/^[[:space:]]*//')
                
                # 根据关键词选择颜色
                if echo "$MESSAGE" | grep -qi "BLOCK\|拦截"; then
                    COLOR=$RED
                    ICON="🚫"
                elif echo "$MESSAGE" | grep -qi "WARNING\|警告\|HIGH_RISK"; then
                    COLOR=$YELLOW
                    ICON="⚠️ "
                elif echo "$MESSAGE" | grep -qi "PASS\|通过\|LOW_RISK"; then
                    COLOR=$GREEN
                    ICON="✅"
                elif echo "$MESSAGE" | grep -qi "risk\|风险\|score"; then
                    COLOR=$BLUE
                    ICON="📊"
                elif echo "$MESSAGE" | grep -qi "已启用\|initialized"; then
                    COLOR=$GREEN
                    ICON="🟢"
                else
                    COLOR=$NC
                    ICON="  "
                fi
                
                echo -e "${COLOR}${ICON} ${MESSAGE}${NC}"
            done <<< "$NEW_CONTENT"
            
            TOTAL_SHOWN=$((TOTAL_SHOWN + NEW_LINES))
        fi
        
        LAST_LINE="$CURRENT_LINE"
    fi
    
    sleep 1
done
