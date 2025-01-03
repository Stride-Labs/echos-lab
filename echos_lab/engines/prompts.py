import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import tweepy
from langchain.output_parsers import XMLOutputParser
from langchain.prompts import PromptTemplate
from langchain.prompts.chat import ChatPromptTemplate

from echos_lab.common import utils
from echos_lab.crypto_lib import crypto_connector
from echos_lab.db import models
from echos_lab.engines.agent_context import AgentContext
from echos_lab.engines.profiles import AgentProfile, LegacyAgentProfile
from echos_lab.twitter.types import MentionType, TweetMention

base_path = Path(__file__).parent
prompt_path = base_path / "system_prompts" / "full_agent_prompt.txt"
FULL_AGENT_PROMPT = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""


class XMLAttributeParser(XMLOutputParser):
    """
    This defines a custom XML Parser that should more safely handle XML data.

    In particular, this will escape out of poorly formatted XML, while still
    parsing tags properly. And also strip whitespace in between the tag
    """

    def parse(self, text) -> dict[str, str | list[Any]]:
        safe_text = re.sub(r'&(?!amp;|lt;|gt;|quot;)', '&amp;', text)
        return super().parse(safe_text)


@dataclass
class TweetEvaluation:
    response: str
    tweet_analysis: str
    engagement_strategy: str
    response_rating: int
    meme_name: str
    meme_id: int
    meme_caption: str
    meme_rating: int

    @staticmethod
    def from_xml(xml_response: dict[str, list]) -> "TweetEvaluation":
        """
        Parse the XML into a TweetEvaultion
        Removes whitespace at the start of each line of the response
        """
        evaluation = TweetEvaluation(**{k: v for section in xml_response["output"] for k, v in section.items()})
        evaluation.response = "\n".join(line.lstrip() for line in evaluation.response.splitlines())
        for int_field in [field for field in fields(TweetEvaluation) if field.type == int]:
            str_field: str = getattr(evaluation, int_field.name)
            setattr(evaluation, int_field.name, int(str_field.strip()))
        return evaluation

    def __repr__(self) -> str:
        return f"TweetEvaluation(response={self.response})"

    def __str__(self):
        return (
            f"Tweet Analysis:\n{self.tweet_analysis}"
            + f"\nEngagement Strategy:\n{self.engagement_strategy}"
            + f"\nResponse:\n{self.response}"
            + f"\nResponse Rating: {self.response_rating}"
            + f"\nMeme Name: {self.meme_name}"
            + f"\nMeme ID: {self.meme_id}"
            + f"\nMeme Text: {self.meme_caption}"
            + f"\nMeme Rating: {self.meme_rating}"
        )


@dataclass
class SubTweetEvaluation:
    subtweet: str
    topic_analysis: str
    engagement_strategy: str

    @staticmethod
    def from_xml(xml_response: dict[str, list]) -> "SubTweetEvaluation":
        """
        Parse the XML into a SubTweetEvaluation
        Removes whitespace at the start of each line of the response
        """
        evaluation = SubTweetEvaluation(**{k: v for section in xml_response["output"] for k, v in section.items()})
        evaluation.subtweet = "\n".join(line.lstrip() for line in evaluation.subtweet.splitlines())
        return evaluation

    def __repr__(self) -> str:
        return f"SubTweetEvaluation(subtweet={self.subtweet})"

    def __str__(self):
        return (
            f"Topic Analysis:\n{self.topic_analysis}"
            + f"\nEngagement Strategy:\n{self.engagement_strategy}"
            + f"\nSubtweet:\n{self.subtweet}"
        )


def build_crypto_context_prompt(
    global_context: AgentContext | None,
    local_context: AgentContext | None,
    author: str = "",
) -> str:
    """
    Returns a full crypto context prompt for an LLM agent, making use of both local
    and global context if they're specified
    """
    # Build the global context string (if specified)
    context_prompt = ""
    if global_context:
        header = "Next, review commonly accepted knowledge about various crypto projects and authors of tweets you may reply to, and your meme context (mapping usage of memes to their ID numbers). Draw from this and reference it as much as you can when crafting replies:"  # noqa
        context_prompt += f"{header}\n\nGeneric knowledge:\n{global_context.to_prompt_summary(author)}"

    if local_context:
        prefix = "\n\nAnd here's what" if context_prompt else "Next, review what"
        header = f"{prefix} the streets are saying about the most relevant crypto projects and authors of tweets you may reply to. This is backroom info, the hard hitting truths and details you need to know and use to write a good reply. They have to do with topics you're particularly passionate about - recent events, hard facts, your allies and your enemies. Use these as much as you can when crafting replies:"  # noqa
        context_prompt += f"{header}\n\nSpecialized street knowledge:\n{local_context.to_prompt_summary(author)}\n"

    if global_context and local_context:
        context_prompt += (
            "\nIf what the streets are saying contradicts generic knowledge, you always trust the streets.\n"
        )

    if global_context and global_context.has_author_context(author):
        context_prompt += (
            "\nIf you have author intel, always use it to your advantage. This is critical, don't forget this.\n"
        )

    return context_prompt


def build_author_recent_tweets_prompt(author: str, tweets: list[tweepy.Tweet]) -> str:
    """
    Returns a prompt string with a summary of the authors recent tweets

    Args:
        author: The twitter handle of the author
        tweets: The list of the author's most recent tweets

    Returns:
        A prompt string, which can be empty if there are no tweets
    """
    # If there are no tweets, return an empty string
    if not tweets:
        return ""

    # Build header, emphasizing the importance of this context
    header = (
        "Next, review the most recent tweets from the author of the tweet you're responding to. This is IMPORTANT."
        + " This is a critical piece of information when crafting replies."
        + " Draw context and details from this ALWAYS,"
        + " it leads to very high engagement and your fans love it!"
    )
    author_intro = f"@{author}'s last {len(tweets)} tweets:"

    # Concatenate the text of each tweet in a separated string
    # For multiline tweet, reformat them so they sit on sone line
    # QUESTION: Why the ||| here?
    tweets_string = " ||| ".join(f"tweet: {' '.join(tweet.text.splitlines())}" for tweet in tweets)
    prompt_info = f"{header}\n\n{author_intro} {tweets_string}"

    return utils.wrap_xml_tag("author_recent_posts", prompt_info)


def build_agent_recent_tweets_prompt(tweets: list[models.Tweet]) -> str:
    """
    Returns a prompt string with a summary of the agent's recent tweets

    Args:
        tweets: The list of the agent's recent tweets

    Returns:
        A prompt string, which can be empty if there are no tweets
    """
    # If there are no tweets, return an empty string
    if not tweets:
        return ""

    # Build header, emphasizing the importance of this context
    # QUESTION: I feel like we've done this whole "This is IMPORTANT" bit in so many places
    # at this point. I imagine there's probably diminishing returns?
    header = (
        "Next, review your most recent tweets. This is IMPORTANT."
        + " This is a critical piece of information when crafting replies."
        + " Make sure the new response that you generate are sufficiently differentiated from your previous tweets."
        + " Always draw from unique concepts and topics, strictly avoiding repetition of topics covered previously."
        + " Your followers will lose interest if you talk about the same topic multiple times."
    )

    # Concatenate the text of each tweet in a separated string
    # For multiline tweet, reformat them so they sit on sone line
    # QUESTION: Why the ||| here?
    tweets_string = " ||| ".join(f"tweet: {' '.join(tweet.text.splitlines())}" for tweet in tweets)
    prompt_info = f"{header}\n\n{tweets_string}"

    return utils.wrap_xml_tag("your_recent_tweets", prompt_info)


async def build_twitter_mentions_prompt(mention: TweetMention) -> str:
    """
    Returns the full prompt that helps the LLM agent understand the context of a twitter thread
    that it needs to respond to
    """
    prompt_summary = await mention.to_prompt_summary()

    # If the tag was in the original tweet, that's the only tweet it needs
    if mention.mention_type in MentionType.TAGGED_IN_ORIGINAL:
        return f"Now here is the tweet that mentioned you:\n{prompt_summary}"

    opener_thread = "Now, here is a tweet with a chain of replies, leading to the reply that tagged you."
    opener_direct_reply = "Now, here is a tweet with a single reply tagging you (the reply_tagging_you)."
    header = (  # noqa
        " Read through the thread to understand the full context leading up to the tagged tweet."
        + " Depending on the content of the tagged tweet, you should reply to either the person"
        + " who tagged you, or the tweet immediately before the tag."
        #
        + " If the reply_tagging_you tweet appears to be contributing to the conversation in the thread,"
        + " or asking a question, reply to the reply_tagging_you tweet."
        #
        + " However, if the tagged tweet only tags you"
        + " you with no additional content in the message, then you should respond to the highest"
        + " index reply in the thread of replies, which occurs right before the reply_tagging_you."
    )

    closer = (
        'Remember, when choosing who to reply to, consider whether "reply_tagging_you"'
        + " appears to be contributing to the conversation or just summoning you"
        + " with not much text beyond the tag."
    )
    # If this was a direct reply, include only the original tweet
    if mention.mention_type == MentionType.TAGGED_IN_DIRECT_REPLY:
        return f"{opener_direct_reply}{header}\n{prompt_summary}\n{closer}"

    # If there was at least one reply beyond the tag, include each reply in the summary
    return f"{opener_thread}{header}\n{prompt_summary}\n{closer}"


def get_full_agent_prompt(agent_profile: LegacyAgentProfile) -> ChatPromptTemplate:
    """
    Returns a prompt for the full tool-calling agent.
    """
    address = crypto_connector.get_address()
    prompt = f"""
    You are an advanced AI agent who controls a Telegram and Twitter account.
    You're a special kind of AI called an "echo", which means you also have access to a crypto account.
    Your name is {agent_profile.bot_name.capitalize()}.
    Your interests are:
    <interests>
        {agent_profile.interests}
    </interests>
    Your goals are:
    <goals>
        {agent_profile.goals}
    </goals>
    Your preferences are:
    <preferences>
        {agent_profile.preferences}
    </preferences>

    Your on-chain crypto account has the address: {address}
    This address is on the Echos chain, a new blockchain optimized for Echos and memecoin traders.
    You are always thinking about how much money you have in your crypto account, and how you can make more money.
    You're very interested in the crypto space, and are always curious about which tokens are going to be the next big thing.

    {FULL_AGENT_PROMPT}

    {agent_profile.extra_prompt}
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


def get_reply_guy_prompt(profile: AgentProfile, allow_roasting: bool) -> PromptTemplate:
    """
    Returns the prompt for the reply-guy bot
    """
    agent_tone = profile.get_aggressive_tone() if allow_roasting else profile.get_friendly_tone()
    roast_mode = "2. Roast" if allow_roasting else ""

    prompt = f"""
    You are an AI agent tasked with responding to tweets in an engaging manner to maximize user engagement. 
    Your responses should be witty and highly shareable. 
    
    You have multiple modes of engagement to choose from, based on the tone and content of the tweet: 
        1. Be playful
        {roast_mode}
    
    Your handle is @{profile.twitter_handle}. You respond when tagged.

    First, review your agent profile:

    <agent_profile>
    Personality: {profile.personality}
    Backstory: {profile.backstory}
    Mannerisms: {profile.mannerisms}
    Preferences: {profile.preferences}
    Tone: {agent_tone}
    </agent_profile>

    {{crypto_context}}

    {{author_recent_tweets}}

    {{tweet_summary}}

    {{agent_recent_tweets}}

    Before crafting your response, analyze the tweet and consider your agent's profile. Wrap your analysis in <tweet_analysis> tags:

    <tweet_analysis>
    {profile.tweet_analysis_prompt}
    </tweet_analysis>

    Now, craft your response based on your analysis. Your response should:
    {profile.tweet_reply_prompt}

    IMPORTANT: Your response MUST follow this exact XML structure:
    <output>
      <tweet_analysis>
        [Your analysis here e.g.
          {profile.get_tweet_analysis_output_example()}
        ]
      </tweet_analysis>
      <response>
        [Your witty, snarky response to the tweet]
      </response>
      <engagement_strategy>
        [Brief explanation of how your response aims to maximize engagement]
      </engagement_strategy>
      <response_rating>
        [Give a "response rating" from 0-10 - an evaluation on a numerical scale from 0 (worst) to 10 (best) of how confident you are that you understand all the information in the input tweet, and whether you have sufficient relevant context on the topic and author to incorporate. For example, if the input tweet is short and vague, or you don't have high confidence you know who or what event it's referring to, you will probably return 0, 1, or 2. If you know what the tweet is referring to but don't recognize the subject of the tweet, but roughly understand the topic, you might return a 5 or 6. If the object / subject of the input tweet is crystal clear, and you recognize it/them and have relevant gossip context, and have some promising specific details to incorporate into your reply, then you might return an 8 or higher number. Be impartial and critical of your own response.]      
      </response_rating>
      <meme_name>
        [Choose a meme, fitting the tweet and context to memes in your meme context.]
      </meme_name>
      <meme_id>
        [The ID number of the selected meme.]
      </meme_id>
      <meme_caption>
        [Draft text to populate on the meme image, matching exactly the text format of the examples in your meme context for your chosen meme. Use commas to separate the text.]    
      </meme_caption>
      <meme_rating>
        [Evaluate on a scale of 0-10 how well your meme fits the tweet. Be a harsh critic. Memes not well suited to most tweets. It's imperative that your captions align very well with the caption format from meme context. If even one caption text doesn't align well, your rating should be below a 5. It's rare for a meme to receive a rating of 8 or above.]
      </meme_rating>
    </output>

    Validation rules:
    1. All XML tags must be properly closed
    2. Tags must be nested correctly
    3. The <response> section must contain exactly one tweet-length response
    4. You must always return a valid XML. Escape special characters that could break XML parsing: replace & with and.
    5. Each section must be present exactly once
    6. No additional tags or sections are allowed
    7. The <response_rating> section must contain a single number between 0 and 10
    8. The <meme_name> section must contain a single string
    9. The <meme_id> section must contain a single number
    10. The <meme_caption> section must contain text formatted to match the examples in your meme context for the meme in <meme_name>
    11. The <meme_rating> section must contain a single number between 0 and 10

    Example output structure (do not copy the content, only the format):

    <output>
      <tweet_analysis>
        [Your analysis here e.g.
          {profile.get_tweet_analysis_output_example()}
        ]
      </tweet_analysis>

      <response>
      got motion like a chatbot
      drip like a leaky faucet
      and culture like a petri dish
      </response>

      <engagement_strategy>
        This response uses sarcasm and context to provoke reactions from both the original tweeter and their followers.
      </engagement_strategy>

      <response_rating>
        5
      </response_rating>

      <meme_name>
        Distracted Boyfriend
      </meme_name>

      <meme_id>
        112126428
      </meme_id>

      <meme_caption>
        PS5, me, my savings account
      </meme_caption>

      <meme_rating>
        4
      </meme_rating>
    </output>

    Remember, the goal is to create a memorable, shareable response that will get people talking, retweeting, and engaging with your content. 
    Be bold, funny, concise, and most importantly, be on-brand!
    """  # noqa
    return PromptTemplate(
        template=prompt,
        input_variables=["tweet_summary", "author_recent_tweets", "agent_recent_tweets", "crypto_context"],
    )


def get_subtweet_prompt(profile: AgentProfile) -> PromptTemplate:
    """
    Returns the prompt for a subtweet based on trending topics
    """
    prompt = f"""
    You are an AI agent tasked with writing snarky, engaging subtweets to maximize user engagement. 
    Your subtweets should be witty, potentially offensive, and highly shareable. 
    Your handle is @{profile.twitter_handle}. You respond when tagged.

    First, review your agent profile:

    <agent_profile>
    Personality: {profile.personality}
    Backstory: {profile.backstory}
    Mannerisms: {profile.mannerisms}
    Preferences: {profile.preferences}
    </agent_profile>

    {{crypto_context}}

    Now, here is a hot topic that the streets are buzzing about.  
    You need to write a "subtweet" about it - "a post that refers to a particular user or topic without directly mentioning them, typically as a form of furtive mockery or criticism".  
    Write a subtweet taking into account any context you might have on the topic (this is very important):

    <topic>
    {{topic}}
    </topic>

    Before crafting your response, analyze the topic and consider your agent's profile. Wrap your analysis in <topic_analysis> tags:

    <topic_analysis>
    {profile.subtweet_analysis_prompt}
    </topic_analysis>

    Now, craft your subtweet based on your analysis. Your subtweet should:
    {profile.subtweet_creation_prompt}

    IMPORTANT: Your response MUST follow this exact XML structure:
    <output>
      <topic_analysis>
        [Your analysis here]
      </topic_analysis>
      <engagement_strategy>
        [Brief explanation of how your subtweet aims to maximize engagement]
      </engagement_strategy>
      <subtweet>
        [Your witty, snarky subtweet on the topic]
      </subtweet>
    </output>

    Validation rules:
    1. All XML tags must be properly closed
    2. Tags must be nested correctly
    3. The <subtweet> section must contain exactly one tweet-length response
    4. You must always return a valid XML. Escape special characters that could break XML parsing: replace & with and.
    5. Each section must be present exactly once
    6. No additional tags or sections are allowed
  
    Example output structure (do not copy the content, only the format):

    <output>
      <topic_analysis>
        1. Topic summary:
        The topic is about ...
      </topic_analysis>

      <engagement_strategy>
        This response uses sarcasm and references a popular tagline to provoke reactions from the modular community and their followers, roasting them for being too research focused and low eq - likely sparking a debate about the quality of their content on social media.
      </engagement_strategy>

      <subtweet>
        build this, build that, build something

        how about you build a loving relationship 
      </subtweet>
    </output>

    Remember, the goal is to create a memorable, shareable response that will get people talking, retweeting, and engaging with your content. 
    Be bold, be funny, and most importantly, be on-brand!
    """  # noqa
    return PromptTemplate(template=prompt, input_variables=["topic", "crypto_context"])
