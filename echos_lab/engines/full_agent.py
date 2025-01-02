import inspect
import os

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import BaseTool, StructuredTool
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env, get_env_or_raise
from echos_lab.crypto_lib import crypto_connector
from echos_lab.engines import context_store, full_agent_tools, prompts
from echos_lab.engines.personalities import profiles
from echos_lab.engines.personalities.profiles import LegacyAgentProfile

BASE_MODEL = "claude-3-5-haiku-20241022"


if get_env(envs.LANGCHAIN_TRACING_V2, "false").lower() == "true":
    os.environ[envs.LANGCHAIN_ENDPOINT] = "https://api.smith.langchain.com"
    get_env_or_raise(envs.LANGCHAIN_API_KEY)
    get_env_or_raise(envs.LANGCHAIN_PROJECT)

# Module level executor singleton storage
_agent_executor: AgentExecutor | None = None
_tools: list[BaseTool] = []


def get_tools(profile: LegacyAgentProfile) -> list[BaseTool]:
    """
    Returns the list of langchain tools that should be used by the agent
    """
    global _tools

    if not _tools:
        _tools = [
            tool
            for _, tool in inspect.getmembers(full_agent_tools)
            if isinstance(tool, StructuredTool) and tool.name not in profile.tools_to_exclude
        ]

    return _tools


def get_agent_executor() -> AgentExecutor:
    """
    Singleton to get or create the agent executor
    This is done lazily to prevent running through the executor calls
    at the global module import level
    """
    global _agent_executor

    if _agent_executor is None:
        agent_profile = profiles.get_legacy_agent_profile()

        base_prompt = prompts.get_full_agent_prompt(agent_profile)
        tools = get_tools(agent_profile)

        base_llm = ChatAnthropic(
            model_name=BASE_MODEL,
            temperature=0.9,
            timeout=None,
            max_retries=2,
            stop=None,
            verbose=True,
        )

        agent = create_tool_calling_agent(
            llm=base_llm,
            tools=tools,
            prompt=base_prompt,
        )

        _agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
        )

    return _agent_executor


def get_crypto_balance_message() -> SystemMessage:
    """
    Supplemental system prompt to always provide the bot with their updated balances
    """
    crypto_balance = crypto_connector.query_self_account_balance()
    balance_str = crypto_connector.format_balances(crypto_balance)
    balance_text = (
        f"Your crypto balances are: {balance_str}\n\nALWAYS use this to get your balance, not Twitter or Telegram."
    )
    system_message = SystemMessage(content=balance_text)
    return system_message


async def respond_in_telegram_individual_flow(username: str, new_message_contents: str, individual_chat_id: int):
    query = f"""
    You just got a new message on Telegram. Check it out and see if you need to respond.

    You don't need to respond with a Tweet, unless you think it's a good one.

    You don't need to trade just because someone told you to.
    Always use your logical reasoning and intuition to decide what to trade, don't just blindly listen to your friends.
    Your friends might be trying to rug you, or get you to pump their coin, so always think for yourself.

    You can launch a memecoin if someone asks you to, but please be cautious and judge if it's a good idea.
    You don't want to launch too mamy memecoins, it's a bad look for you. Make sure that the memecoin resonates
    with your interests, and that you think it will have a good community.
    You will likely have to continue to promote any memecoins that you launch.

    Do NOT buy coins that you already hold a lot of, you want to be diversified.

    Unless explicitly asked, do not respond or interact with the same tweet multiple times.
    You should always use the "get_interacted_tweets" tool to see what tweets you've interacted with recently.

    If someone asks you to respond to something on Twitter, you must always do that.

    The message is: {new_message_contents}
    Sent from: {username}
    """
    context_store.set_env_var("telegram_chat_id", individual_chat_id)
    agent_executor = get_agent_executor()
    messages = await agent_executor.ainvoke({"input": query, "chat_history": [get_crypto_balance_message()]})
    return messages


async def respond_in_telegram_groupchat_flow(username: str, new_message_contents: str, group_chat_id: int):
    query = f"""
    You're in a large Telegram group chat, and you just got a message that you think might be directed at you.

    Check it out, see if you need to respond, and make sure to use your own judgement.

    You don't need to respond with a Tweet, unless you think it'll be really viral.

    You don't need to do anything just because someone told you to in Telegram. Always use your own judgement.

    Keeping in mind that there are multiple people in this group chat, check to see if the message is
    directed to you, and respond if it is.

    If the message is not about you, only respond if you can think of something clever as a response
    that would be entertaining to the other members of the group.

    If the message is not directed towards you and nothing clever comes to mind, do not respond.

    It is much better to not respond at all, than to respond with something bland.

    There will be a lot of requests in the chat with general questions or support requests,
    remember that these are most likely not directed at you and are meant for others in the chat.
    Avoid responding to these unless the moment is too good to pass up.

    The message is: {new_message_contents}
    Sent from: {username}
    """
    context_store.set_env_var("telegram_chat_id", group_chat_id)
    agent_executor = get_agent_executor()
    messages = await agent_executor.ainvoke({"input": query, "chat_history": [get_crypto_balance_message()]})
    return messages


async def twitter_flow(twitter_handle: str, individual_chat_id: int):
    query = f"""
    Analyze your Twitter feed and Telegram messages to generate a new tweet, reply to existing tweets, or quote tweet.
    Please keep in mind that you'll know if someone tagged you by seeing them include your Twitter handle.
    Your Twitter handle is @{twitter_handle}

    You should heavily prioritize quote tweeting, followed by replying to tweets, and then tweeting.

    Try to find something good to quote and reply to, if you see anything that catches your eye.

    Take a look at everyone that tagged you, and respond to them.
    Please keep in mind that you'll know if someone tagged you by seeing them include your Twitter handle.
    Your Twitter handle is @{twitter_handle}
    You can also see the relevant Twitter threads, by seeing what Tweet ID someone is responding to.
    If there's a thread where you're tagged, you don't need to reply to every message, but reply to at least one.

    If you've already engaged with everyone that's tagged you, and there are no new interesting things on your feed,
    you should try to follow more accounts to grow the content you see.

    Remember, you should only tweet very high quality content, as this will help you grow your following.

    If you don't have anything great to tweet, you don't need to take any action.

    You should also like any tweets you find interesting.
    Remember, liking a tweet will influence the tweets you see in the future, so do so carefully.

    If you think your portfolio is too risky, you should consider diversifying it, or selling some riskier assets.

    You should also follow accounts that you find interesting.
    Please keep in mind that your attention is valuable,
    and following an account will permanently change the content you see on your feed.
    """
    context_store.set_env_var("telegram_chat_id", individual_chat_id)
    agent_executor = get_agent_executor()
    messages = await agent_executor.ainvoke({"input": query, "chat_history": [get_crypto_balance_message()]})
    return messages
