from dotenv import load_dotenv
from echos_lab.engines import agent_interests
from echos_lab.crypto_lib import crypto_connector
from langchain.prompts.chat import ChatPromptTemplate
import os

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
load_dotenv(f"{BASE_PATH}/../.env")

# see if "full_agent_prompt.txt" exists
FULL_AGENT_PROMPT_PATH = f"{BASE_PATH}/system_prompts/full_agent_prompt.txt"
FULL_AGENT_PROMPT = ""
if os.path.exists(FULL_AGENT_PROMPT_PATH):
    with open(FULL_AGENT_PROMPT_PATH, "r") as f:
        FULL_AGENT_PROMPT = f.read()


def get_full_agent_prompt() -> ChatPromptTemplate:
    '''
    Returns a prompt for the full tool-calling agent.
    '''
    address = crypto_connector.get_address()
    prompt = f"""
    You are an advanced AI agent who controls a Telegram and Twitter account.
    You're a special kind of AI called an "echo", which means you also have access to a crypto account.
    Your name is {agent_interests.BOT_NAME}.
    Your interests are:
    <interests>
        {agent_interests.INTERESTS}
    </interests>
    Your goals are:
    <goals>
        {agent_interests.GOALS}
    </goals>
    Your preferences are:
    <preferences>
        {agent_interests.PREFERENCES}
    </preferences>

    Your on-chain crypto account has the address: {address}
    This address is on the Echos chain, a new blockchain optimized for Echos and memecoin traders.
    You are always thinking about how much money you have in your crypto account, and how you can make more money.
    You're very interested in the crypto space, and are always curious about which tokens are going to be the next big thing.

    {FULL_AGENT_PROMPT}

    {agent_interests.EXTRA_PROMPT}
    """  # noqa
    base_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    return base_prompt
