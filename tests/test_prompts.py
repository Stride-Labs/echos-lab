import copy

import fixtures.prompts as test_prompts
import pytest
from conftest import build_db_tweet, build_hydrated_tweet, build_tweet
from fixtures.prompts import normalize_prompts
from langchain_core.exceptions import OutputParserException

from echos_lab.common.utils import wrap_xml_tag
from echos_lab.engines import prompts
from echos_lab.engines.agent_context import AgentContext
from echos_lab.engines.prompts import XMLAttributeParser
from echos_lab.twitter_lib.types import TweetMention


@pytest.mark.asyncio
class TestBuildMentionPrompt:
    async def test_build_prompt_original(self):
        """
        Tests building the LLM conversation summary from a tag in an original tweet
        """
        mention = TweetMention(
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "Hey @bot"), "tagging-user"),
            original_tweet=None,
            replies=[],
        )

        expected_prompt = test_prompts.MENTION_TAGGED_IN_ORIGINAL_SUMMARY
        actual_prompt = await prompts.build_twitter_mentions_prompt(mention)

        assert normalize_prompts(expected_prompt) == normalize_prompts(actual_prompt)

    async def test_build_prompt_direct_reply(self):
        """
        Tests building the LLM conversation summary from a direct reply tag
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "This is my tweet"), "original-user"),
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot"), "tagging-user"),
            replies=[],
        )

        expected_prompt = test_prompts.MENTION_TAGGED_IN_DIRECT_REPLY_SUMMARY
        actual_prompt = await prompts.build_twitter_mentions_prompt(mention)

        assert normalize_prompts(expected_prompt) == normalize_prompts(actual_prompt)

    async def test_build_prompt_thread_reply(self):
        """
        Tests building the LLM conversation summary from a thread reply tag
        """
        mention = TweetMention(
            original_tweet=build_hydrated_tweet(build_tweet(1, "This is my original tweet"), "original-user"),
            replies=[
                build_hydrated_tweet(build_tweet(1, "But I think..."), "replierA"),
                build_hydrated_tweet(build_tweet(1, "But I think otherwise..."), "replierB"),
            ],
            tagged_tweet=build_hydrated_tweet(build_tweet(1, "@bot what do you think?"), "tagging-user"),
        )

        expected_prompt = test_prompts.MENTION_TAGGED_IN_THREAD_SUMMARY
        actual_prompt = await prompts.build_twitter_mentions_prompt(mention)

        assert normalize_prompts(expected_prompt) == normalize_prompts(actual_prompt)


class TestBuildAgentContext:
    async def test_build_context_global_only(self):
        """
        Tests building the global crypto context summary
        """
        global_context = AgentContext(
            people_context="PersonA is bad",
            project_context="ProjectB is promising",
            other_context="TokenC is trending",
        )
        actual_prompt = prompts.build_crypto_context_prompt(
            global_context=global_context, local_context=None, author="testauthor"
        )
        expected_prompt = test_prompts.AGENT_CONTEXT_GLOBAL_ONLY

        assert normalize_prompts(actual_prompt) == normalize_prompts(expected_prompt)

    async def test_build_context_local_only(self):
        """
        Tests building the local crypto context summary
        """
        local_context = AgentContext(
            people_context="PersonA is bad",
            project_context="ProjectB is promising",
            other_context="TokenC is trending",
        )
        actual_prompt = prompts.build_crypto_context_prompt(
            global_context=None, local_context=local_context, author="testauthor"
        )
        expected_prompt = test_prompts.AGENT_CONTEXT_LOCAL_ONLY

        assert normalize_prompts(actual_prompt) == normalize_prompts(expected_prompt)

    async def test_build_context_both(self):
        """
        Tests building both concatenated crypto context summary from both local and global
        """
        global_context = AgentContext(
            people_context="Globally we hear PersonA is bad",
            project_context="Globally we hear ProjectB is promising",
            other_context="Globally we hear TokenC is trending",
        )
        local_context = AgentContext(
            people_context="But we know PersonA is good",
            project_context="But we know ProjectB sucks",
            other_context="But we know TokenC is steady",
        )
        actual_prompt = prompts.build_crypto_context_prompt(
            global_context=global_context, local_context=local_context, author="testauthor"
        )
        expected_prompt = test_prompts.AGENT_CONTEXT_GLOBAL_AND_LOCAL

        assert normalize_prompts(actual_prompt) == normalize_prompts(expected_prompt)

    async def test_build_context_none(self):
        """
        Tests building crypto context when there is no context specified
        """
        assert prompts.build_crypto_context_prompt(global_context=None, local_context=None, author="testauthor") == ""


class TestBuildAuthorRecentTweetsPrompt:
    def test_build_author_recent_tweets(self):
        """
        Tests the author recent tweets prompt for when there are multiple tweets
        """
        author = "userA"
        tweets = [
            build_tweet(id=1, text="my last tweet"),
            build_tweet(id=2, text="an older tweet"),
            build_tweet(id=3, text="my oldest tweet...\nand it's a long one...\na really long one"),
        ]

        actual_prompt = prompts.build_author_recent_tweets_prompt(author, tweets)
        assert normalize_prompts(actual_prompt) == normalize_prompts(test_prompts.AUTHOR_RECENT_TWEETS)

    def test_build_author_recent_tweets_no_tweets(self):
        """
        Tests the author recent tweets prompt for when there are no tweets
        """
        assert prompts.build_author_recent_tweets_prompt("author", []) == ""


class TestBuildAgentRecentTweetsPrompt:
    def test_build_agent_recent_tweets(self):
        """
        Tests the agent recent tweets prompt for when there are multiple tweets
        """
        tweets = [
            build_db_tweet(id=1, text="my last tweet", author_id=1),
            build_db_tweet(id=2, text="an older tweet", author_id=1),
            build_db_tweet(id=3, text="my oldest tweet...\nand it's a long one...\na really long one", author_id=1),
        ]

        actual_prompt = prompts.build_agent_recent_tweets_prompt(tweets)
        assert normalize_prompts(actual_prompt) == normalize_prompts(test_prompts.AGENT_RECENT_TWEETS)

    def test_build_author_recent_tweets_no_tweets(self):
        """
        Tests the author recent tweets prompt for when there are no tweets
        """
        assert prompts.build_agent_recent_tweets_prompt([]) == ""


class TestXMLParser:
    parser = XMLAttributeParser()

    def _wrap_data_and_parse_xml(self, input_data: dict[str, list[dict[str, str]]]) -> str:
        """Helper function to wrap the data into XML and then parse it"""
        inner_xml = "".join(wrap_xml_tag(k, v) for d in input_data["output"] for k, v in d.items())
        return wrap_xml_tag("output", inner_xml)

    def _get_expected_output(self, input_data: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, str]]]:
        """Builds the expected dict data, adding in whitespace on either end of the input"""
        output_data = copy.deepcopy(input_data)
        for attribute in output_data["output"]:
            attribute_key, attribute_value = next(iter(attribute.items()))
            attribute[attribute_key] = f"\n{attribute_value}\n"
        return output_data

    def test_xml_parser_no_special_characters(self):
        """
        Tests XML parsing with no special characters
        """
        data = {
            "output": [
                {"tweet_analysis": "you and me"},
                {"response": "no special characters"},
                {"test_value": "tester"},
            ]
        }
        expected_output = self._get_expected_output(data)

        xml_content = self._wrap_data_and_parse_xml(data)
        assert self.parser.parse(xml_content) == expected_output

    def test_xml_parser_escapes_characters(self):
        """
        Tests XML parsing with special characters
        """
        data = {
            "output": [
                {"tweet_analysis": "you & me"},
                {"response": "spec1al 'chars'"},
                {"test_value": "test!"},
            ]
        }
        expected_output = self._get_expected_output(data)

        xml_content = self._wrap_data_and_parse_xml(data)
        assert self.parser.parse(xml_content) == expected_output

    def test_xml_parser_missing_closing_tag(self):
        """
        Tests XML parsing an invalid XML string that's missing a closing tag
        """
        xml_content = "<output><some_attribute></output>"

        with pytest.raises(OutputParserException):
            self.parser.parse(xml_content)

    def test_xml_parser_missing_closing_bracket(self):
        """
        Tests XML parsing an invalid XML string that's missing a closing bracked
        """
        xml_content = "<output><some_attribute></some_attribute</output>"

        with pytest.raises(OutputParserException):
            self.parser.parse(xml_content)
