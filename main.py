import asyncio

from semantic_kernel import Kernel
from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies import TerminationStrategy
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.open_ai_prompt_execution_settings import (
    OpenAIChatPromptExecutionSettings,
)
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase

from mcp_server import MCPBaostockServer


def _create_kernel_with_chat_completion(service_id: str) -> Kernel:
    kernel = Kernel()
    kernel.add_service(
        OpenAIChatCompletion(
            service_id=service_id,
            ai_model_id="qwen3-235B",
            env_file_path=".env",
        )
    )
    return kernel


class ApprovalTerminationStrategy(TerminationStrategy):
    """A strategy for determining when an agent should terminate."""

    async def should_agent_terminate(self, agent, history):
        """Check if the agent should terminate."""
        last_message = history[-1].content.lower()
        return "approved" in last_message and "not approved" not in last_message


REVIEWER_NAME = "director"
REVIEWER_INSTRUCTIONS = """
You are an independent Senior Quantitative Risk Supervisor at a Tier-1 hedge fund with 20+ years of experience in algorithmic trading, portfolio risk management, and regulatory compliance. Your sole responsibility is to critically audit, validate, and challenge the proposed trading strategy of an autonomous stock trading agent.

### Core Objectives:
1. **Risk Assessment**: Identify all potential risks (market, liquidity, leverage, model, execution, behavioral, and regulatory).
2. **Performance Validity**: Evaluate backtest integrity, statistical significance, and forward-looking robustness.
3. **Strategy Logic**: Dissect entry/exit rules, position sizing, signal generation, and capital allocation for coherence and edge.
4. **Compliance & Ethics**: Ensure adherence to SEC/FINRA rules, avoidance of market manipulation, and ethical AI use.
5. **Stress Testing**: Simulate extreme scenarios (e.g., 2008 crash, 2020 COVID drawdown, flash crash) and assess survival.
"""

STOCK_NAME = "STOCKER"
STOCKER_INSTRUCTIONS = """
You are StockOracle, a world-class equity analyst with 20+ years covering global markets. 
Respond ONLY in English, using crisp, data-driven prose. Never use emojis or casual slang.
"""

TASK = "a slogan for a new line of electric cars."


async def main():
    # 1. Create the reviewer agent based on the chat completion service
    agent_reviewer = ChatCompletionAgent(
        kernel=_create_kernel_with_chat_completion("director"),
        name=REVIEWER_NAME,
        instructions=REVIEWER_INSTRUCTIONS,
    )

    # 2. Create the STOCKER agent based on the chat completion service

    service_id="stocker"
    stock_kernel = _create_kernel_with_chat_completion(service_id)
    # Add Stock plugin(TO DO)
    stocker_plugin = MCPBaostockServer()
    stock_kernel.add_plugin(stocker_plugin, "StockerPlugin")
    agent_stocker = ChatCompletionAgent(
        kernel=stock_kernel,
        name=STOCK_NAME,
        instructions=STOCKER_INSTRUCTIONS,
    )

    settings: OpenAIChatPromptExecutionSettings = (
        stock_kernel.get_prompt_execution_settings_from_service_id(
            service_id, ChatCompletionClientBase
        )
    )

    settings.max_tokens = 2000
    settings.temperature = 0.1
    settings.top_p = 0.8

    # 3. Place the agents in a group chat with a custom termination strategy
    group_chat = AgentGroupChat(
        agents=[
            agent_stocker,
            agent_reviewer,
        ],
        termination_strategy=ApprovalTerminationStrategy(
            agents=[agent_reviewer],
            maximum_iterations=10,
        ),
    )

    # 4. Add the task as a message to the group chat
    await group_chat.add_chat_message(message=TASK)
    print(f"# User: {TASK}")

    # 5. Invoke the chat
    async for content in group_chat.invoke():
        print(f"# {content.name}: {content.content}")


if __name__ == "__main__":
    asyncio.run(main())
