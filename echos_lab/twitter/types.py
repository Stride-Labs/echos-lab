from dataclasses import dataclass
from enum import Enum, auto

from tweepy import Tweet

from echos_lab.db import models


class TweetExclusions(str, Enum):
    RETWEETS = "retweeted"
    QUOTE_TWEETS = "quoted"
    REPLIES = "replies"


class ReferenceTypes(str, Enum):
    REPLY = "replied_to"
    QUOTE = "quoted"
    RETWEET = "retweeted"


class HydratedTweet(Tweet):
    """
    Extends Tweet class to add conviences fields like username
    """

    def __init__(self, tweet: Tweet, username: str | None = None):
        super().__init__(data=tweet.data)
        self._username = username

    def __eq__(self, other: object) -> bool:
        """Equality check for testing only"""
        return other is not None and hasattr(other, "data") and self.data == other.data  # type: ignore

    def __repr__(self):
        return f"<HydratedTweet id={self.id} text={repr(self.text)}>"

    async def to_dict(self) -> dict:
        """Returns the dict representation"""
        return {"data": self.data, "username": await self.get_username()}

    @classmethod
    def from_dict(cls, raw_tweet: dict) -> "HydratedTweet":
        """Creates a new HydratedTweet from a JSON dict"""
        assert "data" in raw_tweet, "JSON input to hydrated tweet must have 'data' key"
        return cls(Tweet(data=raw_tweet["data"]), raw_tweet.get("username"))

    @property
    def has_media(self) -> bool:
        """Returns true if the tweet has an image or video"""
        return hasattr(self, "attachments") and self.attachments and "media_keys" in self.attachments

    async def get_username(self) -> str:
        """Get's the username by querying the API with the author ID"""
        # lazy import to prevent circular dependency
        from echos_lab.twitter.twitter_client import get_username_from_user_id

        # If we previously fetched the username, return that one
        if self._username:
            return self._username

        # Otherwise, fetch it via the API and store it if it's found
        username = await get_username_from_user_id(user_id=self.author_id)
        if username:
            self._username = username

        # Return "Unknown" if it's not found
        return username or "Unknown"


class MentionType(str, Enum):
    # original tweet is the tagged tweet
    TAGGED_IN_ORIGINAL = auto()
    # original tweet -> tagged tweet as reply
    TAGGED_IN_DIRECT_REPLY = auto()
    # original tweet -> some other tweets -> tagged tweet
    TAGGED_IN_THREAD = auto()


@dataclass
class TweetMention:
    """
    Stores all the relevant context during a reply-guy tag
    """

    # The main tweet that tagged the bot
    tagged_tweet: HydratedTweet
    # In the event of a reply, the original tweet
    original_tweet: HydratedTweet | None
    # In the event of a reply, the list of each response in the thread
    replies: list[HydratedTweet]

    @property
    def mention_type(self) -> MentionType:
        """Returns the mention type based on the metadata"""
        # If there's no original tweet, that means there are no replies and
        # the tag is in the original tweet
        if self.original_tweet is None:
            return MentionType.TAGGED_IN_ORIGINAL

        # If there is a original tweet, but there are no replies, then it was
        # a direct response
        if self.original_tweet and not self.replies:
            return MentionType.TAGGED_IN_DIRECT_REPLY

        # Otherwise, if there is both a original tweet and replies,
        # then this was a full thread
        return MentionType.TAGGED_IN_THREAD

    async def to_dict(self) -> dict:
        """Returns the dict representation"""
        return {
            "tagged_tweet": await self.tagged_tweet.to_dict(),
            "original_tweet": await self.original_tweet.to_dict() if self.original_tweet else None,
            "replies": [await reply.to_dict() for reply in self.replies],
        }

    @classmethod
    def from_dict(cls, raw_mention: dict) -> "TweetMention":
        """Builds a new TweetMention from a JSON dict"""
        assert "tagged_tweet" in raw_mention
        original_tweet_raw = raw_mention.get("original_tweet")
        tagged_tweet = HydratedTweet.from_dict(raw_mention["tagged_tweet"])

        original_tweet = HydratedTweet.from_dict(original_tweet_raw) if original_tweet_raw else None
        replies = [HydratedTweet.from_dict(reply) for reply in raw_mention.get("replies", [])]

        return cls(tagged_tweet=tagged_tweet, original_tweet=original_tweet, replies=replies)

    async def to_prompt_summary(self):
        """
        Conditionally builds the conversation summary for the LLM agent based on
        the type of mention
        """
        tagger_username = await self.tagged_tweet.get_username()

        # If the tag was in the original tweet, that's the only tweet it needs
        if self.mention_type == MentionType.TAGGED_IN_ORIGINAL:
            return f"""
        <tweet>
        @{tagger_username}
        {self.tagged_tweet.text}
        </tweet>
        """

        # If it wasn't a tag in the original, the original tweet must be non-None
        assert self.original_tweet is not None
        original_username = await self.original_tweet.get_username()

        # If this was a direct reply, include the original tweet and the reply tagging you
        if self.mention_type == MentionType.TAGGED_IN_DIRECT_REPLY:
            return f"""
        <original_tweet>
        @{original_username}
        {self.original_tweet.text}
        </original_tweet>
        <reply_tagging_you>
        @{tagger_username}
        {self.tagged_tweet.text}
        </reply_tagging_you>
        """

        # If there were multiple replies, include each reply in the summary
        async def _get_reply_segment(index: int, reply: HydratedTweet) -> str:
            author = await reply.get_username()
            return f"""
        <reply_{index}>
        @{author}
        {reply.text}
        </reply_{index}>
        """

        replies_summary = "".join([await _get_reply_segment(i, reply) for i, reply in enumerate(self.replies, start=1)])

        return f"""
        <original_tweet>
        @{original_username}
        {self.original_tweet.text}
        </original_tweet>
        {replies_summary}
        <reply_tagging_you>
        @{tagger_username}
        {self.tagged_tweet.text}
        </reply_tagging_you>
        """  # noqa


@dataclass
class FollowerTweet:
    """
    Stores additional context about a tweet from a follower
    """

    tweet: models.Tweet
    username: str

    def to_prompt(self) -> str:
        return f"""Now here is the tweet:

        <tweet>
        @{self.username}
        {self.tweet.text}
        </tweet>
        """  # noqa
