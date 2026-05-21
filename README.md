# Taiji Agent 2.0

**融合 Hermes Agent + cgast/harness + Taiji Verify**
太极哲学驱动的 AI Agent 框架

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/xiejianjun000/taiji-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/xiejianjun000/taiji-agent/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/xiejianjun000/taiji-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/xiejianjun000/taiji-agent)
[![CodeFactor](https://www.codefactor.io/repository/github/xiejianjun000/taiji-agent/badge/main)](https://www.codefactor.io/repository/github/xiejianjun000/taiji-agent/overview/main)
[![PyPI version](https://badge.fury.io/py/taiji-agent.svg)](https://badge.fury.io/py/taiji-agent)
[![Downloads](https://static.pepy.tech/badge/taiji-agent)](https://pepy.tech/project/taiji-agent)
[![GitHub Stars](https://img.shields.io/github/stars/xiejianjun000/taiji-agent?style=social)](https://github.com/xiejianjun000/taiji-agent/stargazers)

> 太极生两仪，两仪生四象，四象生八卦。
> 开源 AI Agent 框架，融合多框架精华，专注防幻觉与可靠性。

---

## 🧘 设计哲学

### 道：三大设计原则

Taiji Agent 的每一行代码，都遵循这三条设计原则：

| 原则 | 解释 | 工程体现 |
|------|------|----------|
| **分布式** | 没有上帝节点，每个 Agent 都是独立主体 | Agent Loop + 事件驱动，无共享状态，消息传递通信 |
| **可进化** | 系统不是「写完」的，是「长出来」的 | 自我学习闭环，人格持续迭代，记忆动态增长 |
| **自组织** | 没有中央调度，智能体自己决定做什么 | Skills Hub 自创建，任务自规划，上下文自组装 |

### 无极：无限扩展的插件化架构

> 无极而太极，太极本无极也

Taiji Agent 的核心只有一件事：**管理 Agent 的生命周期**。所有其他能力都是插件：

- 想加一个新的 LLM？写个 Provider，50 行代码搞定
- 想加一个新的消息渠道？实现 `PlatformAdapter` 接口
- 想加一个新的记忆后端？实现 `HonchoMemory` 就行
- 想加一个新的技能？放到 Skills Hub 自动加载

核心永远轻量，能力无限扩展。这就是无极之道。

---

## 🔮 太极生两仪：阴阳平衡的核心机制

> 一阴一阳之谓道

### ☀️ 阳：确定性 — Taiji Verify 防幻觉系统

**阳是规则，是秩序，是可验证的确定性**。

Taiji Verify 符号层防幻觉系统，是 Taiji Agent 的确定性基石，也是项目中**最核心的差异化能力**。

```
┌───────────────────────────────────────────────────────────────────┐
│                      Taiji Verify 防幻觉五重验证                    │
├────────────────┬───────────────────┬──────────────┬───────────────┤
│  TaijiVerifier │ SelfConsistency   │ SourceTracer │ Hallucination │
│  符号层规则验证  │ 多路径自一致性检查  │ 知识溯源索引  │ 幻觉风险检测器  │
└────────────────┴───────────────────┴──────────────┴───────────────┘
```

- **符号层规则验证 (TaijiVerifier)**：基于知识库的事实匹配，支持正则表达式匹配，输出必须在知识边界内。
- **多路径自一致性 (SelfConsistencyChecker)**：对同一问题采样多次，投票选出一致结果。
- **知识溯源索引 (SourceTracer)**：每个结论都能追溯到原始知识来源，可审计。
- **幻觉风险检测 (HallucinationDetector)**：综合评分 = TaijiVerify(40%) + 自一致性(30%) + 知识溯源(30%)。

### 🌙 阴：随机性 — LLM 创造力引擎

**阴是变化，是创造，是不可预测的可能性**。

Taiji Agent 不造轮子，我们用最好的引擎：

```python
from taiji_agent import TaijiAgent, AgentConfig

agent = TaijiAgent(config=AgentConfig(
    provider="anthropic",
    model="claude-sonnet-4-20250514"
))

result = await agent.run("分析这段代码")
```

**已实现适配器**：

| 适配器 | 对应模型 | 厂商 | 状态 |
|--------|---------|------|------|
| AnthropicProvider | Claude 系列 | Anthropic | ✅ 已实现 |
| OpenAIProvider | GPT 系列 | OpenAI | ✅ 已实现 |
| QwenProvider | 通义千问 | 阿里 | ✅ 已实现 |
| GLMProvider | GLM | 智谱 | ✅ 已实现 |
| KimiProvider | Kimi | 月之暗面 | ✅ 已实现 |
| DoubaoProvider | 豆包 | 字节 | ✅ 已实现 |

### ⚖️ 阴阳调和：动态平衡机制

OpenTaiji 最核心的创新：不是让确定性去「限制」随机性，而是让两者**对话**。

```
LLM 输出
    ↓
[幻觉检测器打分] → 分数 < 阈值？
    ↓                  ↓
  直接输出         [自一致性检查] → 3次采样投票
                          ↓
                    [溯源索引] → 匹配知识库
                          ↓
                    输出 + 来源标注 + 置信度
```

阳中有阴，阴中有阳。这就是太极。

---

## 🎯 核心能力

### 1. Agent Loop — cgast/harness 核心引擎

基于 cgast/harness 的 Universal LLM Agent Runtime，**~350行核心代码**：

```python
from taiji-agent import TaijiAgent

agent = TaijiAgent()  # 默认配置
result = await agent.run("帮我分析代码")
```

### 2. Soul 人格引擎 — YAML 声明式人格定义

安全、可解释、易定制的人格系统：

```yaml
# souls/default.yaml
id: default
name: "太极助手"
layers:
  boundaries:
    - "不产生有害内容"
    - "永远坦诚承认不确定性"
  ethics:
    - "追求阴阳平衡"
  character:
    traits:
      - "深思熟虑"
      - "善于分析"
```

### 3. 记忆系统 — Hermes Honcho 用户建模

跨会话记忆，用户画像，语义搜索：

```python
from taiji-agent import HonchoMemory

honcho = HonchoMemory()
honcho.update_peer_card("user", facts=["喜欢Python"], topic="开发")
context = honcho.get_user_context_prompt()
```

### 4. 自我学习闭环 — 持续进化

从交互中学习，自动创建技能：

```python
from taiji-agent import SelfImprovingLoop

loop = SelfImprovingLoop(honcho, skill_manager, verifier)
learnings = await loop.learn_from_interaction(conversation, task, result, tools)
```

### 5. Skills Hub — 技能市场

开箱即用 + 自定义技能：

| 预置技能 | 说明 |
|---------|------|
| github-auth | GitHub 认证配置 |
| github-pr-workflow | PR 工作流自动化 |
| code-review | 代码审查 |
| web-research | 网络研究 |
| document-writer | 文档写作 |
| chinese-context | 中文语境适配 |
| planning-with-files | 跨会话任务规划 |

### 6. 消息网关 — 多平台支持

| 平台 | 支持 |
|------|------|
| Telegram | ✅ |
| Discord | ✅ |
| Slack | ✅ |
| 企业微信 | ✅ |
| 钉钉 | ✅ |
| 飞书 | ✅ |

### 7. 多智能体协同 — 分布式智能系统

OpenTaiji 支持完整的多智能体协同架构，融合 Hermes Agent Delegate 机制：

#### 协同模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **PARALLEL** | 并行执行，最大并发可配置 | 独立子任务并行处理 |
| **SEQUENTIAL** | 串行执行，按依赖顺序 | 有先后关系的任务链 |
| **HIERARCHICAL** | 层级结构，树形委托 | 任务分解与汇总 |
| **BROADCAST** | 广播模式，一对多 | 通知、公告 |
| **DEBATE** | 辩论模式，多Agent讨论 | 方案评审、决策 |
| **CONSENSUS** | 共识模式，投票决策 | 团队协作、共识达成 |

#### 智能体角色

| 角色 | 功能 |
|------|------|
| **COORDINATOR** | 协调者 - 任务分解和结果汇总 |
| **EXECUTOR** | 执行者 - 具体任务执行 |
| **REVIEWER** | 评审者 - 结果审查 |
| **SYNTHESIZER** | 综合者 - 信息融合 |
| **MONITOR** | 监控者 - 进度跟踪 |

```python
from taiji-agent import MultiAgentCoordinator, AgentRole, AgentTask

coordinator = MultiAgentCoordinator(max_concurrent=3, max_depth=2)

task = AgentTask(description="开发一个电商系统")
result = await coordinator.execute_hierarchical(task)
```

#### 多智能体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Multi-Agent 协同架构                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      MultiAgentCoordinator                       │   │
│  │                        (协调器)                                  │   │
│  │                                                                   │   │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │   │
│  │   │Coder     │  │ Reviewer │  │ Tester   │  │PM        │    │   │
│  │   │ 执行者    │  │ 评审者   │  │ 测试者   │  │ 管理者    │    │   │
│  │   └──────────┘  └──────────┘  └──────────┘  └──────────┘    │   │
│  │                                                                   │   │
│  │   ┌──────────────────────────────────────────────────────┐    │   │
│  │   │                    MessageBus                          │    │   │
│  │   │                 (消息总线/发布订阅)                      │    │   │
│  │   └──────────────────────────────────────────────────────┘    │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│  ┌────────────────────────────────▼─────────────────────────────────┐   │
│  │                         AgentSwarm                                │   │
│  │                     (智能体蜂群 - 动态创建/销毁)                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8. 桌面系统 — 图形界面 + 语音交互

完整的桌面应用程序，支持图形界面和语音对话：

#### 功能特性

| 功能 | 说明 |
|------|------|
| 图形界面 | PyQt6 驱动的 900x650 窗口 + 系统托盘 |
| 绿色吉祥物 | 太极主题的交互式吉祥物 (6种状态) |
| 语音对话 | TTS 语音合成 + STT 语音识别 |
| 唇形同步 | 吉祥物说话时的唇形动画 |
| Lottie 动画 | 平滑的状态切换动画 |

#### 系统要求

| 要求 | 说明 |
|------|------|
| Python | ≥ 3.11 |
| 操作系统 | Windows / macOS / Linux (需要图形环境) |
| 图形库 | PyQt6 依赖 libEGL.so.1 |

#### 安装方式

```bash
# 方式 1: 安装完整桌面版 (推荐)
pip install taiji-agent[desktop,voice]

# 方式 2: 从源码安装
cd taiji-agent
pip install -e ".[desktop,voice]"
```

#### 启动方式

```bash
# 命令行启动
taiji-desktop

# 或直接运行模块
python -m taiji_agent.desktop.main
```

#### 吉祥物状态

| 状态 | 颜色 | Emoji | 说明 |
|------|------|-------|------|
| IDLE | #81C784 | 🟢 | 待机状态 |
| THINKING | #4CAF50 | 💭 | 思考中 |
| SPEAKING | #00E676 | 🗣️ | 说话中 |
| LISTENING | #66BB6A | 👂 | 倾听中 |
| WAITING | #A5D6A7 | ⏳ | 等待中 |
| SLEEPING | #2E7D32 | 😴 | 休眠状态 |

#### 可选依赖

| 依赖 | 安装选项 | 用途 |
|------|---------|------|
| edge-tts | `voice` | 微软语音合成 (中文/英文) |
| faster-whisper | `voice` | Whisper 语音识别 |
| sounddevice | `voice` | 麦克风录音 |

---

## 🧩 项目架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Taiji Agent 2.0                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         用户交互层                                  │   │
│  │  CLI TUI │ Telegram │ Discord │ Slack │ 企业微信 │ 钉钉 │ 飞书     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│  ┌────────────────────────────────▼─────────────────────────────────┐   │
│  │                      太极引擎核心 (Python)                           │   │
│  │                                                                    │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │   │
│  │  │  Taiji Verify │ │     Soul     │ │    Honcho    │              │   │
│  │  │   防幻觉      │ │   人格引擎    │ │   记忆系统    │              │   │
│  │  │ (OpenTaiji) │ │  (Harness)   │ │  (Hermes)    │              │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘              │   │
│  │                                                                    │   │
│  │  ┌──────────────────────────────────────────────────────────────┐  │   │
│  │  │           Agent Loop (Harness ~350行)                        │  │   │
│  │  │      prompt → Taiji Verify验证 → LLM → execute              │  │   │
│  │  └──────────────────────────────────────────────────────────────┘  │   │
│  │                                                                    │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │   │
│  │  │     MCP      │ │   Guardrails │ │  Observability│              │   │
│  │  │  双向协议集成  │ │   安全护栏    │ │   全链路追踪  │              │   │
│  │  │  (Dify v1.6) │ │(OpenAI SDK)  │ │  (LangSmith) │              │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘              │   │
│  │                                                                    │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │   │
│  │  │     HITL     │ │   Workflow   │ │   Handoffs   │              │   │
│  │  │   人机协作    │ │  状态工作流   │ │   Agent交接  │              │   │
│  │  │(Dify v1.13)  │ │  (LangGraph) │ │(OpenAI SDK) │              │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘              │   │
│  │                                                                    │   │
│  │  ┌──────────────┐ ┌──────────────┐                              │   │
│  │  │     Code     │ │    Visual    │                              │   │
│  │  │   代码代理    │ │   工作流可视化 │                              │   │
│  │  │ (SmolAgents) │ │  (Mermaid)   │                              │   │
│  │  └──────────────┘ └──────────────┘                              │   │
│  │                                                                    │   │
│  │  ┌──────────────────────────────────────────────────────────────┐  │   │
│  │  │              工具系统 (15+ Tools)                              │  │   │
│  │  │   文件 │ Shell │ Git │ 搜索 │ 代码执行 │ 记忆 │ ...            │  │   │
│  │  └──────────────────────────────────────────────────────────────┘  │   │
│  │                                                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│  ┌────────────────────────────────▼─────────────────────────────────┐   │
│  │                        模型层 (Multi-Provider)                      │   │
│  │    Anthropic │ OpenAI │ 通义千问 │ GLM │ Kimi │ 豆包              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 模块结构

| 模块 | 来源 | 代码行数 | 功能 |
|------|------|---------|------|
| agent/ | cgast/harness | ~350 | Agent Loop 核心 |
| wfgy/ | OpenTaiji | ~400 | Taiji Verify 防幻觉 |
| souls/ | cgast/harness | ~200 | Soul 人格引擎 |
| memory/ | Hermes | ~150 | 会话记忆 |
| learning/ | Hermes | ~300 | 自我学习闭环 |
| skills/ | Hermes | ~400 | 技能系统 |
| tools/ | Hermes | ~500 | 工具注册表 (15个) |
| providers/ | 通用 | ~200 | LLM 提供商 |
| gateway/ | Hermes | ~400 | 消息网关 |
| events/ | cgast/harness | ~100 | 事件总线 |
| cli/ | Hermes | ~200 | 命令行界面 |

---

## 📥 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/xiejianjun000/taiji-agent.git
cd taiji-agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装基础版
pip install -e "."

# 安装完整版 (包含所有功能)
pip install -e ".[all]"

# 初始化
taiji-agent init
```

### 桌面系统 (可选)

桌面系统提供图形界面和语音交互功能：

```bash
# 安装桌面版依赖
pip install taiji-agent[desktop,voice]

# 启动桌面应用
taiji-desktop
```

> ⚠️ **系统要求**：桌面系统需要本地图形环境 (Windows/macOS/Linux 桌面)，CI 服务器等无图形环境无法运行。

### Taiji Verify 防幻觉验证

```python
from taiji-agent import TaijiVerifier, HallucinationDetector

verifier = TaijiVerifier()
detector = HallucinationDetector()

# 验证内容
passed = verifier.verify("LLM 的输出内容")

# 检测幻觉风险
risk = detector.detect("可能的回复内容")
print(f"幻觉风险: {risk:.1%}")
```

### 运行 Agent

```python
from taiji-agent import TaijiAgent, AgentConfig
import asyncio

async def main():
    config = AgentConfig(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        wfgy_enabled=True,
        max_iterations=25,
    )
    
    agent = TaijiAgent(config=config)
    result = await agent.run("帮我分析这段代码的性能")
    print(result.content)

asyncio.run(main())
```

### 命令行使用

```bash
# 运行 Agent
taiji-agent run "帮我分析这段代码的性能"

# 流式输出
taiji-agent run --stream "写一个快速排序"

# 查看工具
taiji-agent tools

# WFGY 验证
taiji-agent wfgy-check --text "要验证的文本"
```

---

## 🔧 配置

### 环境变量

```bash
# LLM API Keys
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."

# 国产模型 Keys
export DASHSCOPE_API_KEY="..."      # 通义千问
export ZHIPU_API_KEY="..."          # 智谱 GLM
export MOONSHOT_API_KEY="..."       # Kimi
export DOUBAO_API_KEY="..."         # 豆包
```

### 配置 Python

```python
from taiji-agent import AgentConfig

config = AgentConfig(
    provider="anthropic",
    model="claude-sonnet-4-20250514",
    soul="default",
    temperature=0.7,
    max_iterations=25,
    wfgy_enabled=True,
    wfgy_threshold=0.7,
)
```

---

## 🧪 测试

### 运行压力测试

```bash
# Taiji Agent 2.0 新功能测试
python tests/test_v2_features.py

# 完整压力测试
python tests/stress_test.py

# 测试结果
# 新功能测试: 25 通过, 0 失败
# 压力测试: 30 通过, 0 失败
```

### 性能指标

| 模块 | 操作 | 性能 |
|------|------|------|
| Soul 加载 | 1,000次 | 595,860 ops/s |
| Taiji Verify 验证 | 10,000次 | 398,195 ops/s |
| 工具执行 | 100次 | 100,358 ops/s |
| 幻觉检测 | 25,000次 | 102,314 ops/s |
| 并发验证 | 1,000任务 | 234,536 ops/s |

---

## 📖 API 文档

### 主要导出

```python
# 核心
from taiji-agent import (
    TaijiAgent,      # Agent 引擎
    AgentConfig,    # 配置类
)

# Taiji Verify 防幻觉
from taiji-agent import (
    TaijiVerifier,           # 符号层验证器
    HallucinationDetector,  # 幻觉检测器
)

# Soul 人格
from taiji-agent import (
    SoulLoader,    # Soul 加载器
    Soul,          # Soul 数据类
)

# 记忆
from taiji-agent import SessionMemory

# 工具
from taiji-agent import ToolRegistry

# 国产模型
from taiji-agent import (
    QwenProvider,   # 通义千问
    GLMProvider,    # 智谱 GLM
    KimiProvider,   # Kimi
    DoubaoProvider, # 豆包
)

# 消息网关
from taiji-agent import MessageGateway, create_gateway

# 技能系统
from taiji-agent import SkillManager, Skill, SkillCreator

# 自我学习
from taiji-agent import HonchoMemory, SelfImprovingLoop

# 多智能体协同
from taiji-agent import (
    MultiAgentCoordinator,  # 多智能体协调器
    AgentSwarm,            # 智能体蜂群
    MessageBus,            # 消息总线
    AgentRole,             # 智能体角色
    CoordinationMode,      # 协同模式
    AgentMessage,          # 智能体消息
    AgentTask,            # 智能体任务
    BaseAgent,            # 智能体基类
)

# MCP Protocol (Dify v1.6.0)
from taiji-agent import (
    MCPServerAdapter,       # MCP Server 适配器
    MCPServerConfig,       # MCP Server 配置
    MCPClientAdapter,      # MCP Client 适配器
    MCPConnectionConfig,   # MCP 连接配置
    MCPProtocol,          # MCP 协议核心
    MCPTool,              # MCP 工具
    MCPResource,          # MCP 资源
)

# Guardrails (OpenAI Agents SDK)
from taiji-agent import (
    Guardrail,            # 护栏基类
    ValidationResult,      # 验证结果
    GuardrailConfig,      # 护栏配置
    GuardrailManager,     # 护栏管理器
    ContentFilter,        # 内容过滤器
    RateLimitGuardrail,   # 速率限制
    SensitiveDataFilter,  # 敏感数据过滤
    QualityGate,          # 质量门控
)

# Observability (LangSmith)
from taiji-agent import (
    TracingManager,       # 追踪管理器
    TraceSpan,           # 追踪跨度
    TraceEvent,          # 追踪事件
    SpanStatus,          # 跨度状态
    SpanKind,            # 跨度类型
    ConsoleExporter,     # 控制台导出
    FileExporter,        # 文件导出
    LangSmithExporter,   # LangSmith 导出
)

# HITL (Dify v1.13.0)
from taiji-agent import (
    ApprovalQueue,       # 审批队列
    ApprovalRequest,     # 审批请求
    ApprovalDecision,    # 审批决策
    ApprovalStatus,      # 审批状态
    ConfidenceGate,      # 置信度门控
    ConfidenceLevel,     # 置信度级别
    Checkpoint,          # 断点
    CheckpointManager,   # 断点管理器
)

# Workflow (LangGraph)
from taiji-agent import (
    WorkflowEngine,      # 工作流引擎
    WorkflowState,       # 工作流状态
    WorkflowConfig,      # 工作流配置
    NodeResult,          # 节点结果
    WorkflowGraph,       # 工作流图
    Node,                # 节点
    Edge,                # 边
    ConditionalEdge,     # 条件边
)

# Handoffs (OpenAI Agents SDK)
from taiji-agent import (
    Handoff,            # 交接基类
    HandoffConfig,      # 交接配置
    HandoffManager,     # 交接管理器
    HandoffResult,      # 交接结果
    HandoffContext,     # 交接上下文
    AgentRegistry,      # Agent 注册表
)

# Code Agent (SmolAgents)
from taiji-agent import (
    CodeExecutor,       # 代码执行器
    ExecutionResult,    # 执行结果
    ExecutionStatus,    # 执行状态
    SandboxConfig,      # 沙箱配置
    SandboxManager,     # 沙箱管理器
)

# Visual (Mermaid/Graphviz)
from taiji-agent import (
    WorkflowExporter,       # 工作流导出器
    WorkflowExporterFactory,# 导出器工厂
    MermaidExporter,       # Mermaid 导出
    ASCIIExporter,         # ASCII 导出
    JSONExporter,          # JSON 导出
    HTMLExporter,         # HTML 导出
    ExportFormat,          # 导出格式
    WorkflowGraph,         # 工作流图
    NodeData,             # 节点数据
    EdgeData,             # 边数据
)
```

---

## 🗺️ 路线图

### v2.0.0（已完成 ✅）
- [x] Taiji Verify 防幻觉系统
- [x] Soul 人格引擎
- [x] Honcho 记忆系统
- [x] 国产模型支持（通义千问/智谱/Kimi/豆包）
- [x] 消息网关（TG/Discord/企微/钉钉/飞书）
- [x] Skills Hub 技能市场
- [x] 自我学习闭环
- [x] 多智能体协同（6种模式）
- [x] MCP 双向协议集成
- [x] Guardrails 安全护栏
- [x] Tracing 可观测性
- [x] Human-in-the-Loop 人机协作
- [x] Stateful Workflow 状态工作流
- [x] Agent Handoffs 智能体交接
- [x] Code Agent 代码代理
- [x] Visual Workflow 工作流可视化
- [x] **桌面系统 (PyQt6 + 语音交互)**

### v2.1.0（规划中）
- [ ] 完善 WFGY 测试覆盖至 100%
- [ ] 记忆系统持久化（SQLite）
- [ ] 浏览器自动化集成
- [ ] 政务场景定制 (GovMCP)

### v2.5.0（规划中）
- [ ] ~~语音模式 (TTS/STT)~~ ✅ 已集成到桌面系统
- [ ] 人格进化系统
- [ ] 多语言优化

### v3.0.0（愿景）
- [ ] 生产级 Agent 运行时
- [ ] 完整的自我学习闭环
- [ ] 企业级多租户
- [ ] Docker / K8s 部署支持

---

## 🤝 贡献指南

```bash
# 1. Fork 仓库
# 2. 克隆到本地
git clone https://github.com/xiejianjun000/taiji-agent.git
cd taiji-agent

# 3. 安装依赖
pip install -e ".[dev,desktop,voice]"

# 4. 创建功能分支
git checkout -b feature/your-feature

# 5. 运行测试
python -m pytest tests/ -v

# 6. 提交 PR
```

---

## ❓ FAQ

### Q: Taiji Agent 2.0 和 1.0 有什么区别？

**A:** 2.0 版本从 TypeScript 全面迁移到 Python，融合了 Hermes Agent 的全部功能（54+工具、Skills Hub、消息网关、自我学习闭环）和 cgast/harness 的核心引擎（~350行）。WFGY 防幻觉系统作为核心差异化能力保留并增强。

### Q: OpenTaiji 和 LangChain/AutoGen 有什么区别？

**A:** OpenTaiji 的差异化在于：
- **WFGY 防幻觉**：这是独有的，LangChain/AutoGen 没有
- **太极哲学设计**：阴阳平衡，自组织，可进化
- **国产模型优先**：开箱即用支持 6 个主流模型

### Q: 支持哪些国产大模型？

**A:** 已实现 6 个国产模型：
- 通义千问 (QwenProvider)
- 智谱 GLM (GLMProvider)
- Kimi (KimiProvider)
- 豆包 (DoubaoProvider)

### Q: 可以商用吗？

**A:** 可以。OpenTaiji 使用 MIT 许可证。

---

## 💬 社区与联系方式

- 🐙 [GitHub Issues](https://github.com/xiejianjun000/taiji-agent/issues) - Bug 反馈，功能请求

---

## 📄 License

MIT © OpenTaiji Team

---

<div align="center">

**用太极哲学，构建下一代智能系统。**

*道生一，一生二，二生三，三生万物。*

Made with ❤️ by the OpenTaiji Team

</div>

---

*最后更新：2026-05-13*
*文档版本：v2.0*
