from pathlib import Path
from unittest.mock import Mock, patch

from echos_lab.engines.personalities.profiles import (
    AgentProfile,
    AgentTone,
    FollowedAccount,
    LegacyAgentProfile,
)

TEST_PROFILES = "tests/fixtures/profiles"


class TestAgentProfile:
    def _create_profile(self, tone: AgentTone | None) -> AgentProfile:
        """Helper to create profiles with defaults"""
        return AgentProfile(
            name="name",
            model_name="model",
            twitter_handle="@name",
            quote_tweet_threshold=0.0,
            personality="",
            backstory="",
            mannerisms="",
            preferences="",
            tweet_analysis_prompt="",
            tweet_reply_prompt="",
            subtweet_analysis_prompt="",
            subtweet_creation_prompt="",
            tone=tone,
        )

    def test_get_default_tone(self):
        """
        Tests getting the default tone
        """
        assert self._create_profile(None).get_default_tone() is None
        assert self._create_profile(AgentTone(default="")).get_default_tone() is None
        assert self._create_profile(AgentTone(default="chill")).get_default_tone() == "chill"
        assert self._create_profile(AgentTone(default="chill", aggressive="angry")).get_default_tone() == "chill"

    def test_get_subtone_tone(self):
        """
        Tests getting the friendly or aggressive subtones
        """
        assert self._create_profile(None).get_friendly_tone() is None
        assert self._create_profile(AgentTone(default="")).get_friendly_tone() is None
        assert self._create_profile(AgentTone(default="chill")).get_friendly_tone() == "chill"
        assert self._create_profile(AgentTone(default="chill", friendly="happy")).get_friendly_tone() == "chill happy"

        assert self._create_profile(None).get_aggressive_tone() is None
        assert self._create_profile(AgentTone(default="")).get_aggressive_tone() is None
        assert self._create_profile(AgentTone(default="chill")).get_aggressive_tone() == "chill"
        assert self._create_profile(AgentTone(default="chill", aggressive="grr")).get_aggressive_tone() == "chill grr"

    def test_get_tweet_analysis_output_example(self):
        """
        Tests getting the tweet analysis example
        """
        tweet_analysis_prompt = """
            - Some analysis #1:
            [Details for #1]

            - Some analysis #2:
            [Details for #2]

            - Some excluded analysis #3 cause no colon
            [Details for #3]

            Some excluded analysis cause no bullet:
            [Details for #4]
            - Some analysis #5:
        """

        expected_example = """
            - Some analysis #1: ...
            - Some analysis #2: ...
            - Some analysis #5: ...
        """
        expected_example = "\n".join(expected_example.splitlines()[1:-1])  # remove lines with just whitespace

        profile = self._create_profile(None)
        profile.tweet_analysis_prompt = tweet_analysis_prompt

        assert profile.get_tweet_analysis_output_example() == expected_example

        # If the tweet analysis is empty, the example should also be empty
        profile.tweet_analysis_prompt = ""
        assert profile.get_tweet_analysis_output_example() == ""


class TestReadAgentProfiles:
    @patch.object(AgentProfile, "_get_base_config_path", return_value=Path("ignore"))
    @patch.object(AgentProfile, "_get_profile_path", return_value=Path(f"{TEST_PROFILES}/profile.yaml"))
    def test_agent_profile_profile_only(self, mock_profile_path: Mock, mock_base_path: Mock):
        """
        Tests parsing an agent profile yaml, without the base config
        """
        profile = AgentProfile.from_yaml("test")
        assert profile == AgentProfile(
            name="test",
            twitter_handle="test_agent",
            model_name="some_model",
            quote_tweet_threshold=0.1,
            personality="Personality\n",
            backstory="Backstory",
            mannerisms="Mannerisms",
            preferences="Preferences",
            tone=AgentTone(
                default="Default tone",
                aggressive="Aggressive tone",
                friendly="Friendly tone",
            ),
            people_context="Context on person X",
            project_context="Context on project Y",
            other_context="Context on trending topics",
            tweet_analysis_prompt="Tweet analysis prompt",
            tweet_reply_prompt="Tweet reply prompt",
            subtweet_analysis_prompt="Subtweet analysis prompt",
            subtweet_creation_prompt="Subtweet creation prompt",
            followers=[
                FollowedAccount(username="follower1", reply_probability=0.1),
                FollowedAccount(username="follower2", reply_probability=0.2),
            ],
        )

    @patch.object(AgentProfile, "_get_base_config_path", return_value=Path(f"{TEST_PROFILES}/profile.yaml"))
    @patch.object(AgentProfile, "_get_profile_path", return_value=Path("ignore"))
    def test_agent_profile_base_only(self, mock_profile_path: Mock, mock_base_path: Mock):
        """
        Tests parsing a base config yaml, without the agent-specific profile
        """
        profile = AgentProfile.from_yaml("test")
        assert profile == AgentProfile(
            name="test",
            twitter_handle="test_agent",
            model_name="some_model",
            quote_tweet_threshold=0.1,
            personality="Personality\n",
            backstory="Backstory",
            mannerisms="Mannerisms",
            preferences="Preferences",
            tone=AgentTone(
                default="Default tone",
                aggressive="Aggressive tone",
                friendly="Friendly tone",
            ),
            people_context="Context on person X",
            project_context="Context on project Y",
            other_context="Context on trending topics",
            tweet_analysis_prompt="Tweet analysis prompt",
            tweet_reply_prompt="Tweet reply prompt",
            subtweet_analysis_prompt="Subtweet analysis prompt",
            subtweet_creation_prompt="Subtweet creation prompt",
            followers=[
                FollowedAccount(username="follower1", reply_probability=0.1),
                FollowedAccount(username="follower2", reply_probability=0.2),
            ],
        )

    @patch.object(AgentProfile, "_get_base_config_path", return_value=Path(f"{TEST_PROFILES}/profile.yaml"))
    @patch.object(AgentProfile, "_get_profile_path", return_value=Path(f"{TEST_PROFILES}/profile_overrides.yaml"))
    def test_agent_profile_composition(self, mock_profile_path: Mock, mock_base_path: Mock):
        """
        Tests parsing a base config + agent profile yaml
        """
        profile = AgentProfile.from_yaml("test")
        assert profile == AgentProfile(
            name="test",
            twitter_handle="test_agent",
            model_name="some_model",
            quote_tweet_threshold=0.1,
            personality="Personality\n",
            backstory="Backstory",
            mannerisms="Mannerisms",
            preferences="Preferences",
            tone=AgentTone(
                default="Default tone",
                aggressive="Aggressive tone",
                friendly="Friendly tone",
            ),
            people_context="Context on person X",
            project_context="Context on project Y",
            other_context="Context on trending topics",
            tweet_analysis_prompt="Overriding tweet analysis prompt",
            tweet_reply_prompt="Overriding tweet reply prompt",
            subtweet_analysis_prompt="Overriding subtweet analysis prompt",
            subtweet_creation_prompt="Overriding subtweet creation prompt",
            followers=[
                FollowedAccount(username="follower1", reply_probability=0.1),
                FollowedAccount(username="follower2", reply_probability=0.2),
            ],
        )

    @patch.object(AgentProfile, "_get_base_config_path", return_value=Path("notspecified"))
    @patch.object(AgentProfile, "_get_profile_path", return_value=Path(f"{TEST_PROFILES}/profile_defaults.yaml"))
    def test_agent_profile_defaults(self, mock_profile_path: Mock, mock_base_path: Mock):
        """
        Tests parsing an agent profile yaml with default values
        """
        profile = AgentProfile.from_yaml("test")
        assert profile == AgentProfile(
            name="test",
            twitter_handle="test_agent",
            model_name="some_model",
            quote_tweet_threshold=0.1,
            personality="Personality\n",
            backstory="Backstory",
            mannerisms="Mannerisms",
            preferences="Preferences",
            tone=None,
            people_context=None,
            project_context=None,
            other_context=None,
            tweet_analysis_prompt="Tweet analysis prompt",
            tweet_reply_prompt="Tweet reply prompt",
            subtweet_analysis_prompt="Subtweet analysis prompt",
            subtweet_creation_prompt="Subtweet creation prompt",
            followers=[],
        )

    @patch.object(LegacyAgentProfile, "_get_profile_path", return_value=Path(f"{TEST_PROFILES}/legacy_profile.yaml"))
    def test_legacy_agent_profile(self, mock_profile_path: Mock):
        """
        Tests parsing an legacy agent profile yaml
        """
        profile = LegacyAgentProfile.from_yaml("test")
        assert profile == LegacyAgentProfile(
            bot_name="test",
            twitter_handle="test_agent",
            model_name="some_model",
            telegram_invite_link="https://telegram.invite/1",
            interests="Interests\n",
            goals="Goals",
            preferences="Preferences",
            image_tags="tag1, tag2, tag3",
            tools_to_exclude=["tool1", "tool2"],
            extra_prompt="Extra Prompt",
        )
