# Taiji Agent 2.0 集成设计规范

**项目**: taiji-agent
**版本**: 2.0
**日期**: 2026-05-21
**状态**: 设计中

---

## 1. 概述

### 1.1 项目背景

本设计规范涵盖三个核心子系统的集成：
1. **TokenJuice 压缩层** - Token 消耗优化，节省 80% 成本
2. **Memory Tree 分层记忆** - 三层摘要树结构，持久化上下文
3. **桌面系统** - PyQt/PySide 图形界面 + 绿色吉祥物

### 1.2 设计目标

- 将 OpenHuman 的核心功能理念引入 taiji-agent
- 保持 Python 技术栈统一（桌面使用 PyQt）
- 实现绿色太极主题吉祥物动画
- 建立分层架构，便于扩展

### 1.3 技术选型

| 子系统 | 技术选型 | 说明 |
|--------|---------|------|
| TokenJuice | 混合模式 | 规则引擎 + LLM 摘要 |
| Memory Tree | SQLite + Obsidian | 双写存储，同步 Obsidian Vault |
| 桌面系统 | PyQt/PySide | Python 原生 + WebEngine |

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Taiji Agent 2.0                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Presentation Layer (PyQt)                │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐     │    │
│  │  │  Chat UI │ │ Mascot   │ │ System Tray      │     │    │
│  │  │          │ │ (Green)  │ │                  │     │    │
│  │  └──────────┘ └──────────┘ └──────────────────┘     │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                     │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │              Middleware Layer                          │    │
│  │  ┌────────────────┐  ┌────────────────────────────┐   │    │
│  │  │  TokenJuice    │  │  Memory Tree             │   │    │
│  │  │  Compressor    │  │  Hierarchical Summaries  │   │    │
│  │  └────────────────┘  └────────────────────────────┘   │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                     │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │              Core Layer (Agent Engine)                │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌───────────────┐    │    │
│  │  │ Soul System │ │ Tool System │ │ Taiji Verify  │    │    │
│  │  └─────────────┘ └─────────────┘ └───────────────┘    │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 分层职责

| 层级 | 职责 | 组件 |
|------|------|------|
| Presentation | 用户界面交互 | Chat UI、Mascot 动画、系统托盘 |
| Middleware | 数据预处理/后处理 | TokenJuice、Memory Tree |
| Core | Agent Loop 执行 | Engine、Soul、Tools、Taiji Verify |

---

## 3. TokenJuice 压缩层

### 3.1 概述

TokenJuice 是 Token 消耗优化引擎，声称可降低 80% Token 用量。

### 3.2 压缩策略

采用**混合模式**：
- **规则引擎**：适用于所有内容
- **LLM 摘要**：仅当内容 >3k tokens 时触发

### 3.3 规则引擎组件

| 规则 | 输入 | 输出 | 示例 |
|------|------|------|------|
| HTML→Markdown | `<div>text</div>` | `text` | 去除 HTML 标签 |
| URL 缩短 | `https://example.com/very/long/path?params=123` | `[链接]` | 保留可点击性 |
| 去重 | 重复段落 | 单次出现 | 去除冗余 |
| CJK 保留 | 中文/日文/韩文 | 逐字保留 | grapheme-by-grapheme |

### 3.4 LLM 摘要触发条件

```python
TRIGGER_THRESHOLD_TOKENS = 3000

def should_summarize(content: str) -> bool:
    return estimate_tokens(content) > TRIGGER_THRESHOLD_TOKENS
```

### 3.5 API 设计

```python
class TokenJuiceCompressor:
    """TokenJuice 压缩层"""

    def compress(self, content: str, context: str = "") -> CompressedContent:
        """
        压缩内容

        Args:
            content: 原始内容
            context: 当前上下文（用于摘要优化）

        Returns:
            CompressedContent: 压缩后的内容及元数据
        """

    def estimate_savings(self, original: str, compressed: str) -> float:
        """估算节省比例"""
```

### 3.6 文件结构

```
src/taiji_agent/
├── tokenjuice/
│   ├── __init__.py
│   ├── compressor.py      # 主压缩引擎
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── html_to_markdown.py
│   │   ├── url_shortener.py
│   │   ├── deduplicator.py
│   │   └── cjk_preserver.py
│   ├── summarizer.py     # LLM 摘要器
│   └── middleware.py      # 中间件集成
```

---

## 4. Memory Tree 分层记忆

### 4.1 概述

Memory Tree 是分层摘要记忆系统，灵感来自 OpenHuman 的 Hierarchical Summary Trees。

### 4.2 三层结构

```
Memory Tree
│
├── Source Layer (原始层)
│   └── 原始数据：Gmail、GitHub、Notion 等
│
├── Topic Layer (主题层)
│   └── 按主题聚合：项目、人、事件
│
└── Global Layer (全局层)
    └── 高层摘要：用户画像、长期目标、关系图谱
```

### 4.3 数据流

```python
# 数据摄入流程
async def ingest_data(source: DataSource) -> None:
    # 1. 原始数据 → Source Layer
    raw_chunks = chunk_data(source.content, max_tokens=3000)

    # 2. Source → Topic Layer (自动摘要)
    for chunk in raw_chunks:
        topic = await extract_topic(chunk)
        topic_summary = await summarize(chunk)

    # 3. Topic → Global Layer (周期汇总)
    if is_long_interval():
        global_summary = await consolidate_topics()
```

### 4.4 存储设计

#### SQLite Schema

```sql
-- Source Layer
CREATE TABLE source_chunks (
    id TEXT PRIMARY KEY,
    source_type TEXT,
    source_id TEXT,
    content TEXT,
    tokens INTEGER,
    created_at TIMESTAMP,
    accessed_at TIMESTAMP
);

-- Topic Layer
CREATE TABLE topic_summaries (
    id TEXT PRIMARY KEY,
    topic TEXT,
    summary TEXT,
    importance_score REAL,
    last_updated TIMESTAMP
);

-- Global Layer
CREATE TABLE global_memory (
    id TEXT PRIMARY KEY,
    memory_type TEXT,  -- 'persona', 'goal', 'relationship'
    content TEXT,
    confidence REAL,
    updated_at TIMESTAMP
);
```

#### Obsidian Vault 同步

```python
VAULT_DIR = Path.home() / ".taiji" / "vault"

# 文件结构
VAULT_DIR/
├── 📁 sources/
│   └── 📁 {source_type}/
│       └── {source_id}.md
├── 📁 topics/
│   └── {topic}.md
└── 📁 global/
    ├── persona.md
    ├── goals.md
    └── relationships.md
```

### 4.5 API 设计

```python
class MemoryTree:
    """Memory Tree 分层记忆系统"""

    async def ingest(
        self,
        content: str,
        source: DataSource,
        metadata: dict | None = None
    ) -> None:
        """摄入新数据"""

    async def query(
        self,
        query: str,
        layers: list[Layer] | None = None,
        max_tokens: int = 3000
    ) -> str:
        """查询记忆"""

    async def get_context(self, task: str) -> str:
        """获取任务相关上下文"""

    async def sync_vault(self) -> SyncResult:
        """同步 Obsidian Vault"""

    def get_persona(self) -> UserPersona:
        """获取用户画像"""
```

### 4.6 文件结构

```
src/taiji_agent/
├── memory_tree/
│   ├── __init__.py
│   ├── tree.py              # 主 MemoryTree 类
│   ├── layers/
│   │   ├── __init__.py
│   │   ├── source.py        # Source Layer
│   │   ├── topic.py         # Topic Layer
│   │   └── global_.py       # Global Layer
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── sqlite.py        # SQLite 存储
│   │   └── vault.py         # Obsidian Vault 同步
│   ├── summarizer.py        # 摘要生成
│   └── integration.py        # 与 Agent Engine 集成
```

---

## 5. 桌面系统

### 5.1 技术选型

| 组件 | 技术 | 说明 |
|------|------|------|
| GUI 框架 | PyQt6/PySide6 | Python 原生 Qt 绑定 |
| 吉祥物动画 | Lottie Web + QWebEngineView | 复用 OpenHuman 动画资源 |
| 系统托盘 | QSystemTrayIcon | Qt 原生托盘支持 |
| TTS 语音 | edge-tts | 微软语音，绿色主题音色 |
| STT 语音 | faster-whisper | 本地语音识别 |

---

### 5.2 吉祥物语音系统

#### 5.2.1 功能概述

吉祥物不仅能动画展示，还能**说话**、**听指令**，实现真正的语音交互。

#### 5.2.2 TTS 语音合成

```python
class TaijiTTS:
    """太极主题 TTS"""

    def __init__(self):
        self.provider = "edge-tts"
        self.voice = "zh-CN-XiaoxiaoNeural"  # 中文女声
        self.pitch = "+5%"  # 略微提高音调，更活泼
        self.rate = "+10%"  # 略快语速

    async def speak(self, text: str) -> bytes:
        """
        将文本转为语音

        Args:
            text: 要说话的文本

        Returns:
            bytes: WAV/MP3 音频数据
        """
```

#### 5.2.3 音色选择

| 用途 | 推荐音色 | 语言 |
|------|---------|------|
| 默认 | zh-CN-XiaoxiaoNeural | 中文女声 |
| 男性助手 | zh-CN-YunxiNeural | 中文男声 |
| 英文支持 | en-US-JennyNeural | 英文女声 |

#### 5.2.4 STT 语音输入

```python
class TaijiSTT:
    """太极主题 STT"""

    def __init__(self):
        self.model = "base"  # faster-whisper 模型
        self.language = "zh"

    async def listen(self) -> str:
        """
        监听麦克风并识别语音

        Returns:
            str: 识别的文本
        """
        audio = await self.capture_audio()
        text = await self.model.transcribe(audio)
        return text
```

#### 5.2.5 唇形同步

```python
class LipSync:
    """唇形同步动画"""

    def play(self, audio_data: bytes, animation: LottieAnimation):
        """
        播放音频并同步唇形动画

        Args:
            audio_data: TTS 生成的音频
            animation: Lottie 动画对象
        """
        # 1. 播放音频
        self.play_audio(audio_data)

        # 2. 驱动 viseme 映射
        visemes = self.extract_visemes(audio_data)
        for viseme in visemes:
            animation.set_viseme(viseme)
            animation.render_frame()

        # 3. 唇形动画结束
        animation.set_state("idle")
```

#### 5.2.6 语音交互流程

```
用户说话 (STT)
    │
    ▼
┌─────────────────┐
│  faster-whisper  │ ──→ "帮我写一封邮件"
│  本地识别         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Agent 处理      │
│  "正在写邮件..."  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  edge-tts 合成   │ ──→ 音频流
│  绿色音色        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  扬声器播放       │     │  吉祥物唇形动画   │
└─────────────────┘     └─────────────────┘
```

### 5.2 界面布局

```
┌────────────────────────────────────────────────────────────┐
│  🟢 Taiji Agent                              [─] [□] [×]  │
├──────────────┬───────────────────────────────────────────┤
│              │                                            │
│   ┌────┐     │   ┌────────────────────────────────────┐  │
│   │绿色│     │   │                                    │  │
│   │吉祥│     │   │          Chat History              │  │
│   │物  │     │   │                                    │  │
│   │    │     │   │                                    │  │
│   └────┘     │   │                                    │  │
│              │   │                                    │  │
│  状态: 空闲   │   └────────────────────────────────────┘  │
│              │                                            │
│  ┌────────┐  │   ┌────────────────────────────────────┐  │
│  │快捷操作 │  │   │ [输入消息...]                    [▶] │  │
│  └────────┘  │   └────────────────────────────────────┘  │
│              │                                            │
│  ┌────────┐  │   ┌────────────────────────────────────┐  │
│  │记忆查询 │  │   │ Memory Tree: [搜索...] [查看树]      │  │
│  └────────┘  │   └────────────────────────────────────┘  │
│              │                                            │
└──────────────┴───────────────────────────────────────────┘
```

### 5.3 绿色吉祥物设计

#### 主题色

| 用途 | 颜色 | Hex |
|------|------|-----|
| 主色 | 太极绿 | `#4CAF50` |
| 深绿 | 阴面 | `#2E7D32` |
| 浅绿 | 阳面 | `#81C784` |
| 强调 | 活力 | `#00E676` |

#### 吉祥物状态

| 状态 | 动画 | 语音 | 颜色变化 |
|------|------|------|---------|
| 空闲 | 缓慢呼吸 | 静默 | 浅绿脉动 |
| 思考 | 旋转太极 | 静默 | 阴阳旋转 |
| 说话 | 唇形同步 | TTS 播放 | 闪烁高亮 |
| 聆听 | 耳朵倾听 | STT 监听 | 边缘高亮 |
| 等待 | 漂浮 | 静默 | 缓慢上下 |
| 休眠 | 沉睡 | 静默 | 暗淡绿色 |

### 5.5 系统托盘

```python
class TrayManager:
    """系统托盘管理"""

    def create_tray(self):
        """创建托盘图标和菜单"""

    def show_notification(self, title: str, message: str):
        """显示系统通知"""

    def on_tray_click(self, callback: Callable):
        """托盘点击事件"""
```

托盘菜单项：
- 显示/隐藏主窗口
- 快速对话
- 记忆查询
- 设置
- 退出

### 5.6 文件结构

```
src/taiji_agent/
├── desktop/
│   ├── __init__.py
│   ├── main.py              # PyQt 应用入口
│   ├── window.py             # 主窗口
│   ├── chat_view.py          # 聊天视图
│   ├── mascot/
│   │   ├── __init__.py
│   │   ├── widget.py         # 吉祥物 QWidget
│   │   ├── lottie_player.py  # Lottie 动画播放
│   │   ├── states.py         # 状态机
│   │   └── lip_sync.py       # 唇形同步
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── tts.py            # TTS 语音合成
│   │   ├── stt.py            # STT 语音识别
│   │   └── pipeline.py       # 语音管道
│   ├── tray.py               # 系统托盘
│   ├── settings.py           # 设置面板
│   └── assets/
│       ├── mascot/
│       │   ├── idle.json     # 空闲动画
│       │   ├── thinking.json # 思考动画
│       │   ├── speaking.json # 说话动画
│       │   └── sleeping.json # 休眠动画
│       └── icons/
│           └── tray.png
```

### 5.7 PyQt 应用入口

```python
import sys
from PyQt6.QtWidgets import QApplication
from taiji_agent.desktop.window import TaijiWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Taiji Agent")
    app.setStyleSheet(open("theme.qss").read())

    window = TaijiWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

---

## 6. 与 Agent Engine 集成

### 6.1 中间件注入

```python
class AgentConfig:
    # ... 现有配置 ...
    tokenjuice_enabled: bool = True
    tokenjuice_threshold: int = 3000
    memory_tree_enabled: bool = True
    memory_tree_max_context: int = 3000
    desktop_enabled: bool = False
```

### 6.2 请求流程

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  TokenJuice (预处理)                                    │
│  - 压缩工具输出                                         │
│  - 压缩搜索结果                                         │
│  - 压缩长文档                                           │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Agent Loop                                              │
│  - Soul System                                           │
│  - Tool Execution                                        │
│  - Taiji Verify                                          │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Memory Tree (后处理)                                    │
│  - 存储对话摘要                                         │
│  - 更新用户画像                                          │
│  - 同步 Obsidian Vault                                   │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  TokenJuice (后处理)                                    │
│  - 压缩响应                                              │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
Response
```

---

## 7. 依赖更新

### 7.1 pyproject.toml 更新

```toml
[project.optional-dependencies]
# 新增
desktop = [
    "PyQt6>=6.8.0,<7.0.0",
    "lottie>=0.8.0,<1.0.0",
    "qt-material>=2.10.0,<3.0.0",
]
memory = [
    "aiosqlite>=0.20.0,<1.0.0",
    "chromadb>=0.5.0,<1.0.0",  # 可选向量检索
]

[project.optional-dependencies]
# 更新 all
all = [
    "taiji_agent[dev,messaging,voice,browser,desktop,memory]",
]
```

---

## 8. 实施优先级

| 阶段 | 功能 | 预估工时 | 依赖 |
|------|------|---------|------|
| Phase 1 | TokenJuice 压缩层 | 3-5 天 | 无 |
| Phase 2 | Memory Tree 基础 | 5-7 天 | Phase 1 |
| Phase 3 | Memory Tree Obsidian 同步 | 2-3 天 | Phase 2 |
| Phase 4 | PyQt 桌面框架 | 3-5 天 | 无 |
| Phase 5 | 绿色吉祥物动画 | 2-3 天 | Phase 4 |
| Phase 6 | 系统托盘 | 1-2 天 | Phase 4 |

---

## 9. 测试策略

### 9.1 TokenJuice 测试

```python
def test_html_to_markdown():
    """HTML 转 Markdown"""
    input_html = "<p>Hello <b>World</b></p>"
    expected = "Hello **World**"
    assert html_to_markdown(input_html) == expected

def test_token_savings():
    """Token 节省验证"""
    original = "..." # 10k tokens
    compressed = compressor.compress(original)
    savings = (1 - compressed.tokens / 10000) * 100
    assert savings >= 50  # 至少节省 50%
```

### 9.2 Memory Tree 测试

```python
async def test_ingest_and_query():
    """摄入后查询"""
    tree = MemoryTree()
    await tree.ingest("用户喜欢喝咖啡", source=DataSource.GMAIL)
    result = await tree.query("用户偏好")
    assert "咖啡" in result

async def test_vault_sync():
    """Obsidian Vault 同步"""
    tree = MemoryTree()
    result = await tree.sync_vault()
    assert result.files_written > 0
```

### 9.3 集成测试

```python
async def test_full_pipeline():
    """完整流程测试"""
    agent = TaijiAgent(config=AgentConfig(
        tokenjuice_enabled=True,
        memory_tree_enabled=True
    ))
    result = await agent.run("分析我的邮箱")
    assert result.status == TaskStatus.COMPLETED
```

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| TokenJuice LLM 摘要成本 | 高 | 仅对 >3k token 内容使用，缓存摘要 |
| Obsidian Vault 冲突 | 中 | 使用唯一 ID + 时间戳，自动合并 |
| PyQt 跨平台兼容性 | 中 | 测试 Win/Mac/Linux 主要版本 |
| 吉祥物动画性能 | 低 | 使用 Lottie WebEngine 硬件加速 |

---

## 11. 后续扩展

### 11.1 Phase 2 规划

- 多模态输入（图片、语音）
- 语音对话模式
- Auto-fetch 自动同步
- 118+ 第三方集成

### 11.2 Phase 3 规划

- 分布式记忆共享
- 多 Agent 协作
- 自定义吉祥物
- 主题市场

---

**文档版本**: 1.0
**下次审查**: 实施前
**作者**: Taiji Agent Team
