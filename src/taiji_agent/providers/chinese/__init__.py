"""国产大模型全适配 — 11+ 国内主流模型提供商

支持:
  - DeepSeek    (deepseek)        # 已有
  - 通义千问     (qwen/alibaba)    # 已有
  - 智谱 GLM    (glm/zai)          # 已有
  - Kimi        (kimi/moonshot)    # 已有
  - 豆包        (doubao/volcengine)  # 已有
  - 百度千帆     (qianfan/ernie)    # 新增
  - 腾讯混元     (hunyuan/tencent)   # 新增
  - Moonshot    (moonshot)          # 新增
  - MiniMax     (minimax)           # 新增
  - 阶跃星辰     (stepfun)           # 新增
  - 小米        (xiaomi)            # 新增
"""

from taiji_agent.providers.chinese.qianfan import QianfanProvider
from taiji_agent.providers.chinese.hunyuan import HunyuanProvider
from taiji_agent.providers.chinese.moonshot import MoonshotProvider
from taiji_agent.providers.chinese.minimax import MinimaxProvider
from taiji_agent.providers.chinese.stepfun import StepfunProvider
from taiji_agent.providers.chinese.xiaomi import XiaomiProvider

# 已有提供商 - 保持向后兼容
from taiji_agent.providers.chinese.doubao import DoubaoProvider
from taiji_agent.providers.chinese.glm import GLMProvider
from taiji_agent.providers.chinese.kimi import KimiProvider
from taiji_agent.providers.chinese.qwen import QwenProvider

# 已有提供商列表（用于自动发现）
PROVIDER_MAP = {
    "deepseek": "taiji_agent.providers.chinese.deepseek",
    "qwen": "taiji_agent.providers.chinese.qwen",
    "glm": "taiji_agent.providers.chinese.glm",
    "kimi": "taiji_agent.providers.chinese.kimi",
    "doubao": "taiji_agent.providers.chinese.doubao",
    "qianfan": "taiji_agent.providers.chinese.qianfan",
    "hunyuan": "taiji_agent.providers.chinese.hunyuan",
    "moonshot": "taiji_agent.providers.chinese.moonshot",
    "minimax": "taiji_agent.providers.chinese.minimax",
    "stepfun": "taiji_agent.providers.chinese.stepfun",
    "xiaomi": "taiji_agent.providers.chinese.xiaomi",
}

# 提供商元数据（用于 UI 显示和自动发现）
PROVIDER_META = {
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com", "models": ["deepseek-chat", "deepseek-reasoner"]},
    "qwen": {"name": "通义千问 (Qwen)", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "models": ["qwen-plus", "qwen-max", "qwen-turbo"]},
    "glm": {"name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "models": ["glm-4", "glm-4-flash"]},
    "kimi": {"name": "Kimi (月之暗面)", "base_url": "https://api.moonshot.cn/v1", "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]},
    "doubao": {"name": "豆包 (ByteDance)", "base_url": "https://ark.cn-beijing.volces.com/api/v3", "models": ["doubao-pro-32k"]},
    "qianfan": {"name": "百度千帆 (ERNIE)", "base_url": "https://qianfan.baidubce.com/v2", "models": ["ernie-4.0-turbo-8k", "ernie-3.5-8k"]},
    "hunyuan": {"name": "腾讯混元", "base_url": "https://api.hunyuan.cloud.tencent.com/v1", "models": ["hunyuan-pro", "hunyuan-turbo"]},
    "moonshot": {"name": "Moonshot AI", "base_url": "https://api.moonshot.cn/v1", "models": ["moonshot-v1-8k", "moonshot-v1-32k"]},
    "minimax": {"name": "MiniMax", "base_url": "https://api.minimax.chat/v1", "models": ["abab6.5s-chat"]},
    "stepfun": {"name": "阶跃星辰 (StepFun)", "base_url": "https://api.stepfun.com/v1", "models": ["step-2-16k", "step-1-8k"]},
    "xiaomi": {"name": "小米 (MiLM)", "base_url": "https://api.xiaomimlm.com/v1", "models": ["milm-6b"]},
}

__all__ = [
    "QianfanProvider", "HunyuanProvider", "MoonshotProvider",
    "MinimaxProvider", "StepfunProvider", "XiaomiProvider",
    "DoubaoProvider", "GLMProvider", "KimiProvider", "QwenProvider",
    "PROVIDER_MAP", "PROVIDER_META",
]
