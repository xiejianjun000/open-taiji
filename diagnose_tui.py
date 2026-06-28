#!/usr/bin/env python3
"""
TUI 显示问题诊断脚本
检查 _process_stream 和文本输出逻辑是否正常
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

print("="*70)
print("  🔍 TUI 显示问题诊断")
print("="*70)

# ════════════════════════════════════
# 测试1：导入测试
# ════════════════════════════════════
print("\n📋 测试 1: 模块导入")
print("-" * 70)

try:
    from taiji_agent.cli.tui import (
        TaijiTUI,
        StatusBar,
        ChatLog,
        InputBox,
        render_tool_call,
        render_tool_result,
    )
    print("✅ 所有组件导入成功")
except Exception as e:
    print(f"❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ════════════════════════════════════
# 测试2：StatusBar 渲染测试
# ════════════════════════════════════
print("\n📋 测试 2: StatusBar 渲染")
print("-" * 70)

status = StatusBar()
status.model_name = "deepseek-v4-pro"
status.tokens_used = 101000
status.tokens_max = 1000000
status.elapsed = 56.0
status.streaming = True

try:
    rendered = status.render()
    print(f"✅ StatusBar 渲染成功")
    print(f"   输出类型: {type(rendered)}")
    print(f"   内容预览: {str(rendered)[:100]}...")
except Exception as e:
    print(f"❌ StatusBar 渲染失败: {e}")
    import traceback
    traceback.print_exc()

# ════════════════════════════════════
# 测试3：verify_status 更新测试
# ════════════════════════════════════
print("\n📋 测试 3: verify_status 状态更新")
print("-" * 70)

try:
    status.update_verify_status("BLOCK")
    rendered_block = status.render()
    print(f"✅ BLOCK 状态更新成功")
    print(f"   verify_count_blocked = {status.verify_count_blocked}")
    print(f"   包含 '🔴 BLOCK': {'🔴' in str(rendered_block)}")

    status.update_verify_status("HIGH_RISK")
    rendered_warning = status.render()
    print(f"✅ HIGH_RISK 状态更新成功")
    print(f"   verify_count_warned = {status.verify_count_warned}")
    print(f"   包含 '🟠': {'🟠' in str(rendered_warning)}")

except Exception as e:
    print(f"❌ 状态更新失败: {e}")
    import traceback
    traceback.print_exc()

# ════════════════════════════════════
# 测试4：模拟文本输出流程
# ════════════════════════════════════
print("\n📋 测试 4: 模拟文本输出（核心逻辑）")
print("-" * 70)

class MockChat:
    """模拟 ChatLog"""
    def __init__(self):
        self.outputs = []

    def write(self, content):
        self.outputs.append(content)
        if hasattr(content, 'plain'):
            print(f"   📝 写入: {content.plain[:60]}...")
        else:
            print(f"   📝 写入: {str(content)[:60]}...")

class MockStatus:
    """模拟 StatusBar"""
    streaming = True
    def update_verify_status(self, status):
        pass

# 模拟 _process_stream 的关键逻辑
chat = MockChat()
status = MockStatus()

test_chunks = [
    "你好，",  # 普通文本
    "这是一个",  # 普通文本
    "测试消息。\n",  # 带换行的文本
    "第二行内容。",  # 最后一行
]

print("   模拟流式输出:")

current_text_line = ""
full_response = ""

for s in test_chunks:
    print(f"\n   处理 chunk: {repr(s)}")

    # TaijiVerifyPro 检测（简化版）
    if "🚫 [TaijiVerifyPro 拦截]" in s or "[TaijiVerifyPro 拦截]" in s:
        if current_text_line:
            from rich.text import Text
            chat.write(Text(current_text_line, style="white"))
            current_text_line = ""
        print(f"   → 触发 BLOCK 渲染")
        continue

    if "⚠️ [TaijiVerifyPro 警告]" in s or "[TaijiVerifyPro 警告]" in s:
        if current_text_line:
            from rich.text import Text
            chat.write(Text(current_text_line, style="white"))
            current_text_line = ""
        print(f"   → 触发 WARNING 渲染")
        continue

    # 正常文本处理
    current_text_line += s
    full_response += s

    if "\n" in current_text_line:
        parts = current_text_line.split("\n")
        for part in parts[:-1]:
            if part.strip():
                from rich.text import Text
                chat.write(Text(part, style="white"))
        current_text_line = parts[-1]

# 刷新最后一行
if current_text_line.strip():
    from rich.text import Text
    chat.write(Text(current_text_line, style="white"))

print(f"\n✅ 文本输出模拟完成")
print(f"   总输出次数: {len(chat.outputs)}")
print(f"   完整回复长度: {len(full_response)} 字符")

if len(chat.outputs) == 0:
    print("   ❌ 问题：没有任何输出！这可能是 bug 的原因")
else:
    print(f"   ✅ 输出正常")

# ════════════════════════════════════
# 测试5：检查工具调用渲染
# ════════════════════════════════════
print("\n📋 测试 5: 工具调用/结果渲染")
print("-" * 70)

try:
    tool_call = render_tool_call("__TOOL_CALL__:shell;{\"command\": \"ls -la\"}")
    print(f"✅ 工具调用渲染成功: {str(tool_call)[:50]}...")

    tool_result = render_tool_result("__TOOL_RESULT__:total 12345 drwxr-xr-x")
    print(f"✅ 工具结果渲染成功: {str(tool_result)[:50]}...")
except Exception as e:
    print(f"❌ 工具渲染失败: {e}")

# ════════════════════════════════════
# 总结
# ════════════════════════════════════
print("\n" + "="*70)
print("  诊断完成")
print("="*70)
print("""
  如果所有测试都通过：
  → 可能是 taiji-agent 进程需要重启以加载新代码
  
  如果有测试失败：
  → 上面的错误信息会显示具体原因
""")
