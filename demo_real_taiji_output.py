"""
Taiji Agent 真实输出格式演示

这个脚本展示 taiji-agent 的真实输出格式，
与之前的模拟输出完全不同！
"""

import asyncio
from dataclasses import asdict
from taiji_agent.agent.engine import (
    TaijiAgent, 
    AgentConfig, 
    TaskStatus,
    Message
)
from taiji_agent.providers.base import LLMResponse


class RealTaijiProvider:
    """
    符合 taiji-agent 真实接口的 Provider
    """
    
    def __init__(self, model: str = "real-model"):
        self.model = model
    
    async def chat(
        self, 
        messages: list[Message],  # 注意：是 Message 对象，不是 dict！
        tools: list[dict] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """
        真实的 chat 接口
        - messages: Message 对象列表
        - tools: 工具定义列表
        - 返回: LLMResponse 对象
        """
        # 获取用户消息
        user_msg = next(
            (m.content for m in messages if isinstance(m, Message) and m.role == 'user'),
            'Hello'
        )
        
        return LLMResponse(
            content=f"太极助手：收到你的消息「{user_msg[:20]}...」，我现在以你为大脑！",
            tool_calls=None,
            usage={"input_tokens": 50, "output_tokens": 30},
            model=self.model,
            raw={"timestamp": "2026-05-18"}
        )
    
    async def stream_chat(self, messages, **kwargs):
        """流式输出"""
        text = "这是流式响应..."
        for char in text:
            yield char
    
    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4


def print_task_result(result, question_num: int):
    """
    按 taiji-agent 真实格式打印 TaskResult
    """
    print(f"\n{'─'*60}")
    print(f"对话 {question_num} 结果")
    print(f"{'─'*60}")
    
    # 1. 用户输入（如果有）
    # （在实际运行中，用户输入会记录在 messages 中）
    
    # 2. 助手回复
    print(f"助手: {result.content}")
    
    # 3. 状态详情（taiji-agent 真实格式）
    print(f"状态: status={result.status.value}")
    print(f"   迭代: {result.iterations}")
    print(f"   工具: {result.tools_used}")
    print(f"   幻觉风险: {result.hallucination_risk:.2f}")
    print(f"   验证阻止: {result.verify_blocked}")
    
    # 4. 错误信息
    if result.error:
        print(f"错误: {result.error}")
    
    print(f"{'─'*60}\n")


async def main():
    """
    主演示：展示 taiji-agent 真实输出
    """
    print("""
╔═══════════════════════════════════════════════════════════════╗
║            Taiji Agent 真实输出格式演示                        ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # 1. 创建 Agent（真实配置）
    config = AgentConfig(
        model="taiji-assistant",
        stream=False,
        verify_enabled=True,  # 开启验证
        verify_threshold=0.5,
        max_iterations=3,  # 最多3次迭代
        taiji_verify_enabled=False,
        enable_sandbox=True,
        enable_failover=False,
    )
    
    agent = TaijiAgent(config=config)
    agent.provider = RealTaijiProvider()
    
    print("Agent 已初始化")
    print(f"配置: {asdict(config)}")
    print()
    
    # 2. 运行对话
    questions = [
        "你好，请介绍一下自己",
        "太极哲学的核心是什么？",
        "帮我分析这个代码有什么问题"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"👤 用户: {question}")
        
        try:
            result = await agent.run(question)
            print_task_result(result, i)
        except Exception as e:
            print(f"❌ 执行出错: {e}")
    
    # 3. 展示消息历史格式
    print("\n" + "="*60)
    print("消息历史格式（真实 Taiji Agent）")
    print("="*60)
    
    for i, msg in enumerate(agent.messages[:5], 1):  # 只显示前5条
        print(f"{i}. role={msg.role}, content={msg.content[:50]}...")
    
    print("\n✅ 演示完成！")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
