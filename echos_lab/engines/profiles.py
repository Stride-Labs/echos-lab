from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from echos_lab.common.env import ECHOS_HOME_DIRECTORY
from echos_lab.common.env import get_env, get_env_or_raise, EnvironmentVariables as envs

BASE_AGENT_CONFIG = "agent-base.yaml"
DEFAULT_AGENT_PROFILE = "agent-profile.yaml"

PROFILE_CONFIG_HELP = """
By default, agent configs are stored under `~/.echos`;
however, it can be overridden with the `ECHOS_HOME_DIRECTORY` environment variable

If running a single agent, store the agent's profile in `agent-profile.yaml` under the echo's home directory

If running multiple agents, store the shared config under `agent-base.yaml`, store the agent-specific config
under {agent_name}.yaml, and set the `AGENT_NAME` environment variable to the name of your agent
"""


# TODO: Consolidate these two agent profiles
@dataclass
class LegacyAgentProfile:
    """
    Profile for the older agents that use an LLM for all decision making and orchestration
    """

    # Human readable name of the bot (e.g. "Chad")
    bot_name: str
    # Twitter handle
    twitter_handle: str
    # LLM model name
    model_name: str
    # Invite link for telegram
    telegram_invite_link: str
    # Topics the agent is interested in (e.g. crypto, memecoins, etc.), as a bullet point list string
    interests: str
    # Goals of the agent (e.g. go viral), as a bullet point list string
    goals: str
    # Communication style, tone, etc., as a bullet point list string
    preferences: str
    # Descriptive tags to use when generating images (e.g. robot, futuristic), as a comma separated list
    image_tags: str
    # List of custom tool functions that should not be used
    tools_to_exclude: list[str] = field(default_factory=list)
    # TODO: Merge this into something else
    extra_prompt: str = ""
    # TODO: Merge this into something else
    tweet_generation_process: str = ""

    @staticmethod
    def _get_profile_path(agent_name: str | None) -> Path:
        """Get the full path to an agent's yaml profile"""
        agent_file = f"{agent_name}.yaml" if agent_name else DEFAULT_AGENT_PROFILE
        return ECHOS_HOME_DIRECTORY.joinpath(agent_file)

    @classmethod
    def from_yaml(cls, agent_name: str | None) -> "LegacyAgentProfile":
        """
        Load agent profile from a YAML file named agent-profile.yaml or {agent_name}.yaml
        """
        agent_file_path = LegacyAgentProfile._get_profile_path(agent_name)

        if not agent_file_path.exists():
            raise RuntimeError(f"Agent profile not found for '{agent_name}'.\n{PROFILE_CONFIG_HELP}")

        with open(agent_file_path, "r") as f:
            data = yaml.safe_load(f)

        profile = cls(**data)
        return profile


@dataclass
class AgentTone:
    # Baseline tone that should always be used
    default: str = ""
    # Tone adjustments when vying for a friendlier response
    friendly: str | None = None
    # Tone adjustments when vying for a more aggressive response
    aggressive: str | None = None


@dataclass
class FollowedAccount:
    # The twitter username of the account
    username: str
    # The percent of tweets from the account that we should reply to
    # e.g. 0.2 means we'll respond 20% of the time
    # Defaults to replying to all tweets
    reply_probability: float = 1.0


@dataclass
class AgentProfile:
    """
    Profile for the newer reply-guy agents
    """

    # The agent's name (should be the same as the yaml file name)
    name: str
    # The agent's twitter handle
    twitter_handle: str
    # LLM model name
    model_name: str
    # Threshold to quote tweet instead of reply tweet from reply guy
    # e.g. 0.2 means 20% of the time, the reply will be a quote tweet
    quote_tweet_threshold: float
    # Brief summary of the agent's personality
    # e.g. he's a trader... caries himself like ... known for ...
    personality: str
    # The agent's backstory and/or upbringing
    backstory: str
    # Specifics on how the agent communicates
    mannerisms: str
    # Bullet list of interests
    preferences: str
    # Prompt with detailed instructions for how to analyze a tweet
    # It should highlight particular focus areas and walk through a
    # "thought process" that should be help guide the agent towards
    # the desired response
    tweet_analysis_prompt: str
    # Bullet point list of specific instructions to use when generating a reply
    # e.g. "Aim to be funny and increase engagement"
    tweet_reply_prompt: str
    # Prompt with detailed instructions for how to analyze a subtweet topic
    # It should highlight particular focus areas and walk through a "thought
    # process" that should be help guide the agent towards the desired subtweet
    subtweet_analysis_prompt: str
    # Bullet point list of specific instructions to use when generating a subtweet
    # e.g. "Aim to be funny and increase engagement"
    subtweet_creation_prompt: str
    # Tone to use when responding (i.e. aggressive vs friendly)
    tone: AgentTone | None = None
    # Context on different crypto influencers
    # If loading from gsheets, leave blank
    people_context: str | None = None
    # Context on different crypto projects
    # If loading from gsheets, leave blank
    project_context: str | None = None
    # Context on anything else
    # If loading from gsheets, leave blank
    other_context: str | None = None
    # List of user names of accounts that the agent follows and replies to
    followers: list[FollowedAccount] = field(default_factory=list)

    @staticmethod
    def _get_base_config_path() -> Path:
        """Gets the full path to the main agent config"""
        return ECHOS_HOME_DIRECTORY.joinpath(BASE_AGENT_CONFIG)

    @staticmethod
    def _get_profile_path(agent_name: str | None) -> Path:
        """Get the full path to an agent's yaml profile"""
        agent_file = f"{agent_name}.yaml" if agent_name else DEFAULT_AGENT_PROFILE
        return ECHOS_HOME_DIRECTORY.joinpath(agent_file)

    @classmethod
    def from_yaml(cls, agent_name: str | None) -> "AgentProfile":
        """
        Load agent profile from a YAML file named {agent_name}.yaml
        in this same directory
        """
        base_config_path = AgentProfile._get_base_config_path()
        agent_config_path = AgentProfile._get_profile_path(agent_name)

        if not base_config_path.exists() and not agent_config_path.exists():
            raise RuntimeError(f"Agent profile not found for '{agent_name}'.\n{PROFILE_CONFIG_HELP}")

        base_data = {}
        if base_config_path.exists():
            with open(base_config_path, "r") as f:
                base_data = yaml.safe_load(f)

        agent_data = {}
        if agent_config_path.exists():
            with open(agent_config_path, "r") as f:
                agent_data = yaml.safe_load(f)

        profile = cls(**base_data | agent_data)
        profile.tone = AgentTone(**profile.tone) if profile.tone else None  # type: ignore
        profile.followers = [FollowedAccount(**account) for account in profile.followers or []]  # type: ignore
        return profile

    def _get_subtone(self, tone_name: Literal["friendly", "aggressive"]) -> str | None:
        """Returns default plus the specified tone"""
        if not self.tone:
            return None

        default = self.get_default_tone()
        subtone = getattr(self.tone, tone_name)

        if not default and not subtone:
            return None

        if default and not subtone:
            return default

        if not default and subtone:
            return subtone

        return f"{default} {subtone}"

    def get_default_tone(self) -> str | None:
        return self.tone.default if self.tone and self.tone.default else None

    def get_friendly_tone(self) -> str | None:
        return self._get_subtone("friendly")

    def get_aggressive_tone(self) -> str | None:
        return self._get_subtone("aggressive")

    def get_reply_probability(self, username: str) -> float:
        """
        Get the reply probability for a given username.
        Returns 1.0 if the username is not in the follower list or doesn't have an explicit
        reply probability set
        """
        return next((f.reply_probability for f in self.followers if f.username == username), 1.0)

    def get_tweet_analysis_output_example(self) -> str:
        """
        Returns a prompt that's used in the tweet analysis example
        It should just consist of any lines that start with a bullet point ("-")
        and end with a colon

        Ex Analysis:
            - Tweet summary:
              [How would you summarize this tweet]
            - Relation to interests:
              [How does this relate to your interests?]

        Ex Example Prompt:
          - Tweet summary:
          - Relation to interests:
        """
        header_lines = [
            f"{line} ..."
            for line in self.tweet_analysis_prompt.splitlines()
            if line.lstrip().startswith("-") and line.rstrip().endswith(":")
        ]
        return "\n".join(header_lines)


def get_agent_profile() -> AgentProfile:
    """
    Retreives the currently configured agent profile
    """
    agent_name = get_env(envs.AGENT_NAME)
    return AgentProfile.from_yaml(agent_name)


def get_legacy_agent_profile() -> LegacyAgentProfile:
    """
    Retreives the currently configured legacy agent profile
    """
    agent_name = get_env(envs.LEGACY_AGENT_NAME)
    return LegacyAgentProfile.from_yaml(agent_name)


def get_agent_name() -> str:
    """
    Returns the name of the agent from the environment variable
    """
    return get_env_or_raise(envs.AGENT_NAME)
