# Taiji Agent 全功能测试体系

> 融合 Hermes Agent 的严密隔离 + OpenClaw OPC 的分层架构
> 覆盖 12 个系统、19 种工具、11 个国产模型提供商

---

## 一、测试哲学

### 两大来源的精髓

| 来源 | 核心思想 | taiji-agent 继承 |
|------|----------|-----------------|
| **Hermes Agent** | 严密环境隔离、CI 对等、禁止变更检测测试 | conftest.py 全隔离、脚本化运行器 |
| **OpenClaw OPC** | 测试先行、分层架构、模块边界严守 | unit/integration/e2e/stress 四层 |

### 两条铁律

1. **隔离铁律** — 每个测试必须完全独立，不能依赖真实凭据、真实文件系统
2. **无变更检测** — 不硬编码"当前可用模型数 = 11"这类易变断言

---

## 二、测试分层架构

```
┌──────────────────────────────────────────────────────┐
│                    e2e (端到端)                       │
│  真实 API 调用，完整用户流程验证                       │
│  数量: 少而精 (5-10 个场景)                            │
│  条件: 需要 API Key + 网络                             │
├──────────────────────────────────────────────────────┤
│                 stress (压力/并发)                     │
│  多进程并发、边界值、大消息量                           │
│  数量: 针对性 (每个并发场景 1 个)                       │
├──────────────────────────────────────────────────────┤
│               integration (集成测试)                   │
│  Mock LLM，跨模块协作验证                              │
│  数量: 中 (每个系统 2-5 个)                             │
├──────────────────────────────────────────────────────┤
│                 unit (单元测试)                        │
│  纯逻辑，零外部依赖，极快执行                           │
│  数量: 多 (每个模块 5-20 个)                            │
└──────────────────────────────────────────────────────┘
```

---

## 三、12 个系统的测试矩阵

### 系统 1: Agent Engine (核心引擎)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | AgentConfig 验证、Message 序列化、TaskResult 状态 | `unit/test_agent_config.py` |
| unit | 系统提示构建、Soul 注入、消息组装 | `unit/test_agent_prompt.py` |
| unit | 迭代控制、max_iterations 边界 | `unit/test_agent_loop.py` |
| integration | Mock LLM + 无工具简单对话 | `integration/test_agent_conversation.py` |
| integration | Mock LLM + 单工具调用 | `integration/test_agent_tool_use.py` |
| integration | Mock LLM + 多轮工具调用 | `integration/test_agent_multi_tool.py` |
| e2e | 真实 API 简单对话 | `e2e/test_live_conversation.py` |
| e2e | 真实 API 工具链调用 | `e2e/test_live_toolchain.py` |

### 系统 2: 工具系统 (19 Tools)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | ToolRegistry 注册/去重/查询 | `unit/test_tool_registry.py` |
| unit | ToolSchema 序列化/反序列化 | `unit/test_tool_schema.py` |
| unit | 各工具 handler 纯逻辑 | `unit/test_tool_handlers.py` |
| integration | file_read/file_write/file_list 真实 FS | `integration/test_tool_file.py` |
| integration | shell 执行 + 超时控制 | `integration/test_tool_shell.py` |
| integration | git_status/git_log 真实仓库 | `integration/test_tool_git.py` |
| integration | execute_code 沙箱 | `integration/test_tool_code.py` |

### 系统 3: 技能市场 (Skills)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | SkillRegistry 扫描/解析/YAML frontmatter | `unit/test_skill_registry.py` |
| unit | skill_manage CRUD 操作逻辑 | `unit/test_skill_manage.py` |
| unit | 技能名验证、路径穿越防护 | `unit/test_skill_security.py` |
| unit | 出处追踪 (provenance) ContextVar | `unit/test_skill_provenance.py` |
| unit | 技能使用统计 (usage tracker) | `unit/test_skill_usage.py` |
| integration | 创建→查看→编辑→删除 完整流程 | `integration/test_skill_lifecycle.py` |
| integration | 渐进式披露 (Tier 1→2→3) | `integration/test_skill_disclosure.py` |

### 系统 4: 后台审查 (Background Review)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | should_review 判定逻辑 (dict + Pydantic) | `unit/test_review_trigger.py` |
| unit | 记忆价值判断 (_has_memory_value) | `unit/test_review_memory_value.py` |
| integration | 完整审查流程 (非阻塞线程) | `integration/test_review_pipeline.py` |

### 系统 5: 梦境系统 (Dream)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | DreamConfig 配置验证 | `unit/test_dream_config.py` |
| unit | DreamType 枚举 | `unit/test_dream_types.py` |
| unit | MemoryDigester 摘要提取 | `unit/test_dream_digest.py` |
| integration | 手动触发梦境 (trigger_dream) | `integration/test_dream_trigger.py` |
| integration | 自动技能创建 (digest_deep) | `integration/test_dream_skill_creation.py` |

### 系统 6: 定时任务 (Cron)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | 调度表达式解析 (30m/every 2h/cron) | `unit/test_cron_schedule.py` |
| unit | 下次运行时间计算 | `unit/test_cron_next_run.py` |
| unit | CronJobManager CRUD | `unit/test_cron_jobs.py` |
| unit | 提示注入扫描 (_scan_prompt) | `unit/test_cron_security.py` |
| integration | 调度器启动/停止/文件锁 | `integration/test_cron_scheduler.py` |
| integration | 脚本任务执行 + 结果投递 | `integration/test_cron_execution.py` |

### 系统 7: 上下文压缩 (Context)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | 压缩算法 (保护首尾 + 中间摘要) | `unit/test_context_compressor.py` |
| unit | Token 估算 | `unit/test_context_tokens.py` |
| unit | 压缩阈值判断 | `unit/test_context_should_compress.py` |
| unit | dict + Pydantic 消息兼容 | `unit/test_context_message_types.py` |

### 系统 8: 国产模型 (11 Chinese Providers)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | 各 Provider 初始化 + 环境变量读取 | `unit/test_provider_init.py` |
| unit | PROVIDER_MAP/PROVIDER_META 完整性 | `unit/test_provider_metadata.py` |
| unit | UnifiedProviderRegistry 自动发现 | `unit/test_provider_discovery.py` |
| unit | OpenAI→Anthropic 工具格式转换 | `unit/test_provider_tool_conversion.py` |
| integration | Mock HTTP 响应测试各 Provider | `integration/test_provider_mock.py` |
| e2e | 真实 API 调用各 Provider (需 key) | `e2e/test_provider_live.py` |

### 系统 9: IM 网关 (5 Platforms)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | 消息格式转换 (各平台) | `unit/test_im_message_format.py` |
| unit | 签名验证逻辑 | `unit/test_im_signature.py` |
| unit | Webhook 处理 | `unit/test_im_webhook.py` |
| unit | create_gateway 工厂 | `unit/test_im_gateway_factory.py` |
| integration | 飞书消息发送/接收 Mock | `integration/test_im_feishu.py` |

### 系统 10: Taiji Verify (太极验证)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | WFGYVerifier 符号层验证 | `unit/test_verify_wfgy.py` |
| unit | HallucinationDetector 幻觉检测 | `unit/test_verify_hallucination.py` |
| unit | DeltaS 阴阳距计算 | `unit/test_verify_delta_s.py` |
| unit | 五阶段流水线 (Kun/Qian/Fu/Xun/Polaris) | `unit/test_verify_pipeline.py` |
| unit | FailureMode 检测 | `unit/test_verify_failure_modes.py` |
| integration | 完整验证引擎 (带 Mock LLM) | `integration/test_verify_engine.py` |

### 系统 11: 记忆系统 (Memory)

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | SessionMemory CRUD | `unit/test_memory_session.py` |
| unit | 记忆搜索 | `unit/test_memory_search.py` |
| unit | Todo 管理 | `unit/test_memory_todo.py` |
| unit | 用户画像 (peer card) | `unit/test_memory_profile.py` |
| integration | 跨会话持久化 | `integration/test_memory_persistence.py` |

### 系统 12: CLI 与全系统集成

| 层级 | 测试内容 | 文件 |
|------|---------|------|
| unit | 16 个斜杠命令解析 | `unit/test_cli_commands.py` |
| unit | SessionStore 会话管理 | `unit/test_cli_sessions.py` |
| integration | 完整对话流程 (Mock LLM) | `integration/test_cli_conversation.py` |
| integration | 后台审查触发 | `integration/test_cli_review.py` |
| e2e | 开箱即用全流程 (真实 API) | `e2e/test_out_of_box_e2e.py` |
| stress | 长对话上下文压力 | `stress/test_long_conversation.py` |
| stress | 多工具并发调用 | `stress/test_concurrent_tools.py` |

---

## 四、关键测试模式

### 模式 1: Mock LLM 集成测试

```python
@pytest.mark.asyncio
async def test_agent_conversation(mock_llm_provider, agent_config):
    """验证 Agent 能正确处理简单对话"""
    agent = TaijiAgent(config=agent_config)
    agent.provider = mock_llm_provider

    result = await agent.run("你好")

    assert result.status == TaskStatus.COMPLETED
    assert result.content is not None
    assert "太极" in result.content
    assert result.iterations == 0
    assert len(agent.messages) >= 3  # system + user + assistant
```

### 模式 2: dict + Pydantic 双类型兼容

```python
def test_msg_access_both_types():
    """验证 _msg_role 和 _msg_content 兼容两种消息类型"""
    from taiji_agent.agent.engine import Message

    # Pydantic 对象
    pydantic_msg = Message(role="user", content="hello")
    assert _msg_role(pydantic_msg) == "user"
    assert _msg_content(pydantic_msg) == "hello"

    # 普通 dict
    dict_msg = {"role": "tool", "content": "result"}
    assert _msg_role(dict_msg) == "tool"
    assert _msg_content(dict_msg) == "result"
```

### 模式 3: 技能生命周期集成测试

```python
def test_skill_create_view_delete(temp_taiji_home):
    """完整 CRUD 流程"""
    from taiji_agent.skills import SkillRegistry, skill_manage, skills_list

    # 创建
    result = skill_manage(action="create", name="test-skill",
                         content="---\nname: test-skill\ndescription: Test\n---\n\n# Test")
    assert result["success"]

    # 列表
    skills = skills_list()
    assert any(s["name"] == "test-skill" for s in skills)

    # 删除
    result = skill_manage(action="delete", name="test-skill")
    assert result["success"]
```

### 模式 4: 环境隔离验证

```python
def test_no_credential_leak():
    """验证测试环境无凭据泄漏"""
    # 所有 API_KEY 变量应该不存在
    for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"]:
        assert os.getenv(key) is None, f"{key} leaked into test!"
```

---

## 五、运行方式

```bash
# ========== 单元测试 (无网络, 毫秒级) ==========
python -m pytest tests/unit/ -v

# ========== 集成测试 (Mock LLM, 秒级) ==========
python -m pytest tests/integration/ -v

# ========== 全量快速测试 (unit + integration) ==========
python -m pytest tests/unit/ tests/integration/ -v --tb=short

# ========== E2E 测试 (需要 API key) ==========
TAIJI_E2E=1 python -m pytest tests/e2e/ -v --tb=long

# ========== 压力测试 ==========
python -m pytest tests/stress/ -v --timeout=120

# ========== CI 对等运行 (4 并发) ==========
python -m pytest tests/ -q -n 4 --tb=short \
  --ignore=tests/e2e/ \
  --ignore=tests/stress/

# ========== 覆盖率报告 ==========
python -m pytest tests/unit/ tests/integration/ \
  --cov=src/taiji_agent --cov-report=html --cov-report=term
```

---

## 六、覆盖率目标

| 层级 | 覆盖率目标 |
|------|-----------|
| Agent Engine | ≥80% |
| 工具系统 | ≥70% |
| 技能市场 | ≥75% |
| 后台审查 | ≥70% |
| 梦境系统 | ≥60% |
| 定时任务 | ≥75% |
| 上下文压缩 | ≥80% |
| 国产模型 | ≥60% |
| IM 网关 | ≥50% |
| Taiji Verify | ≥70% |
| 记忆系统 | ≥75% |
| CLI | ≥50% |
| **整体** | **≥70%** |

---

## 七、与两个源项目的对比

| 维度 | Hermes Agent | OpenClaw OPC | taiji-agent (本方案) |
|------|-------------|-------------|---------------------|
| 测试框架 | pytest | pytest + vitest | pytest |
| 环境隔离 | 极严格 (凭证+HERMES_HOME+状态重置) | 中等 (conftest fixtures) | 继承 Hermes 极严格 |
| 测试分层 | 按功能目录 | unit/integration/api/e2e | 融合两者 |
| 测试数量 | ~17k tests, ~900 files | ~30 test files (精简) | 目标: 150+ tests |
| 并发运行 | xdist 4 workers | 串行 | xdist 4 (CI) / 串行 (dev) |
| Mock 策略 | unittest.mock | unittest.mock + AsyncMock | 继承两者 |
| CI 集成 | GHA, Docker | GHA | GHA (计划) |
| 禁止变更检测 | 是 (文档明确规定) | 否 | 是 (继承 Hermes) |
| 测试先行 | 否 | 是 (DEVELOPMENT.md 要求) | 是 (继承 OpenClaw) |
