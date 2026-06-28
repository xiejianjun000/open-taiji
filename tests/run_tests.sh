#!/usr/bin/env bash
# =========================================================================
# Taiji Agent Test Runner
# 融合 Hermes Agent 的 CI 对等 + OpenClaw OPC 的分层运行
#
# Usage:
#   ./tests/run_tests.sh                        # 全量 unit + integration
#   ./tests/run_tests.sh tests/unit/            # 仅单元测试
#   ./tests/run_tests.sh tests/unit/test_agent_core.py::TestMessage  # 单个类
#   ./tests/run_tests.sh -v --tb=long           # 透传 pytest 参数
#   E2E=1 ./tests/run_tests.sh tests/e2e/       # E2E (需要 API key)
# =========================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# 查找 Python 环境
PYTHON=""
for candidate in .venv-3.11/bin/python .venv/bin/python python3 python; do
    if command -v "$candidate" &>/dev/null && "$candidate" -c "import sys; sys.exit(0)" 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: No Python interpreter found"
    exit 1
fi

echo "Using Python: $PYTHON"

# 默认参数
DEFAULT_ARGS="-q --tb=short -p no:warnings"
WORKERS=""

# 检查是否在 CI 环境 (GHA 等)
if [ "${CI:-}" = "true" ] || [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    WORKERS="-n 4"
    echo "CI mode: 4 parallel workers"
fi

# 构建 pytest 参数
PYTEST_ARGS="$DEFAULT_ARGS $WORKERS"

# E2E 模式 (需要 API key)
if [ "${E2E:-}" = "1" ]; then
    echo "E2E mode: real API calls enabled"
    export TAIJI_E2E=1
fi

# 默认测试目标
TARGETS="${@:-tests/unit/ tests/integration/}"

echo "Running: $PYTHON -m pytest $PYTEST_ARGS $TARGETS"
echo ""

"$PYTHON" -m pytest $PYTEST_ARGS $TARGETS
