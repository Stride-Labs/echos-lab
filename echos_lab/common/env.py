import os
from pathlib import Path
from typing import TypeVar, overload

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
DOT_ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(DOT_ENV_PATH)

ECHOS_HOME_DIRECTORY = Path(os.getenv("ECHOS_HOME_DIRECTORY", "~/.echos")).expanduser()
ECHOS_HOME_DIRECTORY.mkdir(exist_ok=True)


class EnvironmentVariables:
    # Core echos config
    ECHOS_HOME_DIRECTORY = "ECHOS_HOME_DIRECTORY"
    AGENT_NAME = "AGENT_NAME"
    LEGACY_AGENT_NAME = "LEGACY_AGENT_NAME"

    # Database config
    POSTGRES_DATABASE_URL = "POSTGRES_DATABASE_URL"
    SQLITE_DB_PATH = "SQLITE_DB_PATH"

    # Reply guy response thresholds
    RESPONSE_RATING_THRESHOLD_MENTIONS = "RESPONSE_RATING_THRESHOLD_MENTIONS"
    RESPONSE_RATING_THRESHOLD_FOLLOWERS = "RESPONSE_RATING_THRESHOLD_FOLLOWERS"
    MEME_RATING_THRESHOLD = "MEME_RATING_THRESHOLD"

    # Twitter API keys
    TWITTER_CONSUMER_KEY = "TWITTER_CONSUMER_KEY"
    TWITTER_CONSUMER_SECRET = "TWITTER_CONSUMER_SECRET"
    TWITTER_BEARER_TOKEN = "TWITTER_BEARER_TOKEN"
    TWITTER_ACCESS_TOKEN = "TWITTER_ACCESS_TOKEN"
    TWITTER_ACCESS_TOKEN_SECRET = "TWITTER_ACCESS_TOKEN_SECRET"

    # Google sheets config
    GOOGLE_SHEETS_AUTH = "GOOGLE_SHEETS_AUTH"
    AGENT_CONTEXT_LOCAL_SPREADSHEET_ID = "AGENT_CONTEXT_LOCAL_SPREADSHEET_ID"
    AGENT_CONTEXT_GLOBAL_SPREADSHEET_ID = "AGENT_CONTEXT_GLOBAL_SPREADSHEET_ID"

    # Meme generation config
    IMGFLIP_USERNAME = "IMGFLIP_USERNAME"
    IMGFLIP_PASSWORD = "IMGFLIP_PASSWORD"

    # Slack config
    SLACK_BOT_TOKEN = "SLACK_BOT_TOKEN"
    SLACK_APP_TOKEN = "SLACK_APP_TOKEN"
    SLACK_CHANNEL_ID = "SLACK_CHANNEL_ID"

    # Langchain Tracing
    LANGCHAIN_TRACING_V2 = "LANGCHAIN_TRACING_V2"
    LANGCHAIN_ENDPOINT = "LANGCHAIN_ENDPOINT"
    LANGCHAIN_API_KEY = "LANGCHAIN_API_KEY"
    LANGCHAIN_PROJECT = "LANGCHAIN_PROJECT"

    # Headless twitter config
    TWITTER_COOKIES_PATH = "TWITTER_COOKIES_PATH"
    TWITTER_ACCOUNT = "TWITTER_ACCOUNT"
    TWITTER_PASSWORD = "TWITTER_PASSWORD"
    TWITTER_EMAIL = "TWITTER_EMAIL"

    # Telegram config
    TELEGRAM_TOKEN = "TELEGRAM_TOKEN"
    TELEGRAM_INDIVIDUAL_CHAT_ID = "TELEGRAM_INDIVIDUAL_CHAT_ID"
    TELEGRAM_GROUP_CHAT_ID = "TELEGRAM_GROUP_CHAT_ID"

    # Telegram config for creating a new group
    TELEGRAM_ADMIN_HANDLE = "TELEGRAM_ADMIN_HANDLE"
    TELEGRAM_API_ID = "TELEGRAM_API_ID"
    TELEGRAM_API_HASH = "TELEGRAM_API_HASH"

    # Crypto config
    CRYPTO_ACCOUNT_PATH = "CRYPTO_ACCOUNT_PATH"
    CRYPTO_PRIVATE_KEY_PASSWORD = "CRYPTO_PRIVATE_KEY_PASSWORD"
    CRYPTO_PRIVATE_KEY = "CRYPTO_PRIVATE_KEY"

    # Echo contract config
    ECHOS_CHAIN_ID = "ECHOS_CHAIN_ID"
    ECHOS_CHAIN_RPC = "ECHOS_CHAIN_RPC"
    ECHOS_MANAGER_ADDRESS = "ECHOS_MANAGER_ADDRESS"
    ECHOS_UNISWAP_ROUTER_ADDRESS = "ECHOS_UNISWAP_ROUTER_ADDRESS"
    ECHOS_UNISWAP_FACTORY_ADDRESS = "ECHOS_UNISWAP_FACTORY_ADDRESS"
    ECHOS_WUSDC_ADDRESS = "ECHOS_WUSDC_ADDRESS"
    GOLDKSY_GRAPHQL_ENDPOINT = "GOLDKSY_GRAPHQL_ENDPOINT"

    # LLM config
    OPENPIPE_API_KEY = "OPENPIPE_API_KEY"
    ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"

    # Image generation config
    REPLICATE_API_TOKEN = "REPLICATE_API_TOKEN"
    PINATA_JWT = "PINATA_JWT"


T = TypeVar("T")


@overload
def get_env(variable_name: str) -> str | None: ...


@overload
def get_env(variable_name: str, default_value: T) -> str | T: ...


def get_env(variable_name: str, default_value: T | None = None) -> str | T | None:
    """
    Wrapper around os.getenv to ensure that the .env file has been loaded
    This should be used instead of os.getenv
    """
    return os.getenv(variable_name, default_value)


def get_env_or_raise(variable_name: str) -> str:
    """
    Attempts to fetch and return the environment variable, but errors
    if it's not set
    """
    value = os.getenv(variable_name)
    if not value:
        raise EnvironmentError(f"Environment variable {variable_name} not found, specify in .env file")
    return value
