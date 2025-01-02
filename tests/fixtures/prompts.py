# Desired output for prompts, used in test cases


def normalize_prompts(text: str) -> str:
    """Take care of inconsistent characters on the blank lines"""
    return "\n".join([line.strip() for line in text.splitlines() if line.strip()]).strip()


########################################################################
#                            Mentions                                  #
########################################################################


MENTION_TAGGED_IN_ORIGINAL_SUMMARY = """Now here is the tweet that mentioned you:

        <tweet>
        @tagging-user
        Hey @bot
        </tweet>
"""  # noqa

MENTION_TAGGED_IN_DIRECT_REPLY_SUMMARY = """Now, here is a tweet with a single reply tagging you (the reply_tagging_you). Read through the thread to understand the full context leading up to the tagged tweet. Depending on the content of the tagged tweet, you should reply to either the person who tagged you, or the tweet immediately before the tag. If the reply_tagging_you tweet appears to be contributing to the conversation in the thread, or asking a question, reply to the reply_tagging_you tweet. However, if the tagged tweet only tags you you with no additional content in the message, then you should respond to the highest index reply in the thread of replies, which occurs right before the reply_tagging_you.

        <original_tweet>
        @original-user
        This is my tweet
        </original_tweet>
        <reply_tagging_you>
        @tagging-user
        @bot
        </reply_tagging_you>

Remember, when choosing who to reply to, consider whether "reply_tagging_you" appears to be contributing to the conversation or just summoning you with not much text beyond the tag.
"""  # noqa
MENTION_TAGGED_IN_THREAD_SUMMARY = """Now, here is a tweet with a chain of replies, leading to the reply that tagged you. Read through the thread to understand the full context leading up to the tagged tweet. Depending on the content of the tagged tweet, you should reply to either the person who tagged you, or the tweet immediately before the tag. If the reply_tagging_you tweet appears to be contributing to the conversation in the thread, or asking a question, reply to the reply_tagging_you tweet. However, if the tagged tweet only tags you you with no additional content in the message, then you should respond to the highest index reply in the thread of replies, which occurs right before the reply_tagging_you.

        <original_tweet>
        @original-user
        This is my original tweet
        </original_tweet>

        <reply_1>
        @replierA
        But I think...
        </reply_1>
        
        <reply_2>
        @replierB
        But I think otherwise...
        </reply_2>

        <reply_tagging_you>
        @tagging-user
        @bot what do you think?
        </reply_tagging_you>

Remember, when choosing who to reply to, consider whether "reply_tagging_you" appears to be contributing to the conversation or just summoning you with not much text beyond the tag.
"""  # noqa

########################################################################
#                     Agent Context Individual                         #
########################################################################

AGENT_CONTEXT_ALL = """<crypto_context>

<tweet_author_intel>
We have no author intel about the author of this tweet.
</tweet_author_intel>

<people_context>
PersonA is good
</people_context>

<project_context>
ProjectB is good
</project_context>

<other_context>
TokenC is good
</other_context>

</crypto_context>
"""

AGENT_CONTEXT_PEOPLE_ONLY = """<crypto_context>

<tweet_author_intel>
We have no author intel about the author of this tweet.
</tweet_author_intel>

<people_context>
PersonA is good
</people_context>

</crypto_context>
"""

AGENT_CONTEXT_OTHER_ONLY = """<crypto_context>

<tweet_author_intel>
We have no author intel about the author of this tweet.
</tweet_author_intel>

<other_context>
TokenC is good
</other_context>

</crypto_context>
"""

AGENT_CONTEXT_PEOPLE_AND_OTHER_ONLY = """<crypto_context>

<tweet_author_intel>
We have no author intel about the author of this tweet.
</tweet_author_intel>

<people_context>
PersonA is good
</people_context>

<other_context>
TokenC is good
</other_context>

</crypto_context>
"""

########################################################################
#                       Agent Context Combined                         #
########################################################################

AGENT_CONTEXT_GLOBAL_ONLY = """Next, review commonly accepted knowledge about various crypto projects and authors of tweets you may reply to, and your meme context (mapping usage of memes to their ID numbers). Draw from this and reference it as much as you can when crafting replies:

Generic knowledge:
<crypto_context>

<tweet_author_intel>
We have no author intel about the author of this tweet.
</tweet_author_intel>

<people_context>
PersonA is bad
</people_context>

<project_context>
ProjectB is promising
</project_context>

<other_context>
TokenC is trending
</other_context>

</crypto_context>
"""  # noqa

AGENT_CONTEXT_LOCAL_ONLY = """Next, review what the streets are saying about the most relevant crypto projects and authors of tweets you may reply to. This is backroom info, the hard hitting truths and details you need to know and use to write a good reply. They have to do with topics you're particularly passionate about - recent events, hard facts, your allies and your enemies. Use these as much as you can when crafting replies:

Specialized street knowledge:
<crypto_context>

<tweet_author_intel>
We have no author intel about the author of this tweet.
</tweet_author_intel>

<people_context>
PersonA is bad
</people_context>

<project_context>
ProjectB is promising
</project_context>

<other_context>
TokenC is trending
</other_context>

</crypto_context>
"""  # noqa

AGENT_CONTEXT_GLOBAL_AND_LOCAL = """Next, review commonly accepted knowledge about various crypto projects and authors of tweets you may reply to, and your meme context (mapping usage of memes to their ID numbers). Draw from this and reference it as much as you can when crafting replies:

Generic knowledge:
<crypto_context>

<tweet_author_intel>
We have no author intel about the author of this tweet.
</tweet_author_intel>

<people_context>
Globally we hear PersonA is bad
</people_context>

<project_context>
Globally we hear ProjectB is promising
</project_context>

<other_context>
Globally we hear TokenC is trending
</other_context>

</crypto_context>

And here's what the streets are saying about the most relevant crypto projects and authors of tweets you may reply to. This is backroom info, the hard hitting truths and details you need to know and use to write a good reply. They have to do with topics you're particularly passionate about - recent events, hard facts, your allies and your enemies. Use these as much as you can when crafting replies:

Specialized street knowledge:
<crypto_context>

<tweet_author_intel>
We have no author intel about the author of this tweet.
</tweet_author_intel>

<people_context>
But we know PersonA is good
</people_context>

<project_context>
But we know ProjectB sucks
</project_context>

<other_context>
But we know TokenC is steady
</other_context>

</crypto_context>

If what the streets are saying contradicts generic knowledge, you always trust the streets.
"""  # noqa

########################################################################
#                          Recent Tweets                               #
########################################################################

AUTHOR_RECENT_TWEETS = f"""<author_recent_posts>
Next, review the most recent tweets from the author of the tweet you're responding to. This is IMPORTANT. This is a critical piece of information when crafting replies. Draw context and details from this ALWAYS, it leads to very high engagement and your fans love it!

@userA's last 3 tweets: tweet: my last tweet ||| tweet: an older tweet ||| tweet: my oldest tweet... and it's a long one... a really long one
</author_recent_posts>
"""  # noqa

AGENT_RECENT_TWEETS = f"""<your_recent_tweets>
Next, review your most recent tweets. This is IMPORTANT. This is a critical piece of information when crafting replies. Make sure the new response that you generate are sufficiently differentiated from your previous tweets. Always draw from unique concepts and topics, strictly avoiding repetition of topics covered previously. Your followers will lose interest if you talk about the same topic multiple times.

tweet: my last tweet ||| tweet: an older tweet ||| tweet: my oldest tweet... and it's a long one... a really long one
</your_recent_tweets>
"""  # noqa
