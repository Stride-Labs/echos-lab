import datetime
import json
import os
from pathlib import Path
from typing import cast

from echos_lab.engines import post_maker, prompts
from echos_lab.engines.personalities import profiles
from echos_lab.engines.personalities.profiles import AgentProfile
from echos_lab.engines.post_maker import TweetEvaluation
from echos_lab.twitter import twitter_client
from echos_lab.twitter.types import HydratedTweet, MentionType, TweetMention

CURRENT_DIRECTORY = Path(__file__).parent
INPUT_DIRECTORY = CURRENT_DIRECTORY / "input"
OUTPUT_DIRECTORY = CURRENT_DIRECTORY / "output"

PROMPTS_PY_FILE = CURRENT_DIRECTORY.parent / "engines" / "prompts.py"

SECTION_DIVIDER = "------------------------------------------------------------------------------"


async def generate_tweet_examples(links_file, tweets_file):
    """
    Given a text file with a list of tweet links, queries each of them
    and writes them out to a JSON that can be used to test prompts
    """
    with open(INPUT_DIRECTORY / links_file, "r") as f:
        links = [line.strip() for line in f.readlines()]

    # Query each tweet and store it in the TweetMention JSON representation
    mentions = []
    for link in links:
        tweet_id = int(link.split("/")[-1])
        tweet = await twitter_client.get_tweet_from_tweet_id(tweet_id)
        assert tweet, f"Tweet not found from link {link}"

        mention = await twitter_client.enrich_user_mention(tweet)
        mentions.append(await mention.to_dict())

    # Write each TweetMention JSON to the input folder
    with open(INPUT_DIRECTORY / tweets_file, "w") as f:
        json.dump(mentions, f, indent=4)


# TODO: This is very hacky, find a better solution
def get_prompt_source_code(agent_profile: AgentProfile) -> str:
    """
    Returns the full prompt source code function as a string
    This is so we can keep track of which prompt was used without
    actually evaluation the prompt (and thus reducing the output size)
    """
    prompt_function = "get_reply_guy_prompt"

    # Read prompts.py
    with open(PROMPTS_PY_FILE, "r") as f:
        lines = f.readlines()

    # Get the start and end index of the function
    # NOTE: This assumes the function ends with a line that starts with "return PromptTemplate"
    start_index = next(i for i, line in enumerate(lines) if f"def {prompt_function}" in line)
    end_index = next(i for i, line in enumerate(lines) if i > start_index and "return PromptTemplate" in line)
    assert start_index and end_index, "Function or return statement not found"

    # Get the full text string of the function
    function_source_code = "".join(lines[start_index : end_index + 1])  # noqa

    return function_source_code


async def get_response(agent_profile: AgentProfile, mention: TweetMention) -> TweetEvaluation:
    """
    Generates the LLM response for a given tweet mention
    """
    # Extract the original tweet that's the main tweet that we should respond to
    is_original_tweet = mention.mention_type == MentionType.TAGGED_IN_ORIGINAL
    original_tweet = mention.tagged_tweet if is_original_tweet else cast(HydratedTweet, mention.original_tweet)

    # Extract the author and generate the summary prompt
    author = await original_tweet.get_username()

    # if the author is a large account, fetch more historical tweets before responding
    is_large_account = await twitter_client.has_high_follower_count(original_tweet.author_id)
    num_author_tweets = 15 if is_large_account else 5
    author_recent_tweets, _ = await twitter_client.get_tweets_from_user_id(
        original_tweet.author_id, num_tweets=num_author_tweets
    )
    conversation_summary = await prompts.build_twitter_mentions_prompt(mention)

    # Generate a response from the LLM
    evaluation = await post_maker.generate_reply_guy_tweet(
        agent_profile=agent_profile,
        author=author,
        tweet_summary=conversation_summary,
        author_recent_tweets=author_recent_tweets,
        agent_recent_tweets=[],
        allow_roasting=True,
    )
    assert evaluation, "Empty response from LLM"

    return evaluation


async def write_output_file(
    agent_profile: AgentProfile,
    current_time: str,
    output_file: Path,
    mentions: list[TweetMention],
    evaluations: list[TweetEvaluation],
):
    """
    Writes the output file with the responses to each example, in the format:

        Timestamp
        Git Commit Hash
        --------------------------------------
        Responses:

           1. Tweet
           Response

           2. ...
        --------------------------------------
        Thread Summary #1
           ...
        ---
        Tweet Analysis #1
           ...
        --------------------------------------
        Thread Summary #
           ...
        ---
        Tweet Analysis #2
           ...
        --------------------------------------
        Prompt
    """
    assert len(mentions) == len(evaluations), "Not all mentions have a response"

    # Get the current commit hash
    git_hash = os.popen('git rev-parse HEAD').read().strip()

    # Build up the header
    header = f"{current_time}\n{git_hash}\n"

    # Build the response summary
    #
    # ----------------
    # Responses:
    #
    #    1. Tweet: ...
    #
    #    Response: ...
    #    ...
    responses_summary = f"{SECTION_DIVIDER}\nResponses:\n\n"
    for i, (mention, evaluation) in enumerate(zip(mentions, evaluations), start=1):
        tweet_text = mention.original_tweet.text if mention.original_tweet else mention.tagged_tweet.text
        response_text = evaluation.response.strip()
        responses_summary += f"\t{i}. Tweet: {tweet_text}\n\n\tResponse: {response_text}\n\n"

    # Build the tweet analyss
    #
    # --------------------
    # Tweet #1:
    #    ... {thread summary}
    #
    # Thread Analysis:
    #    ...
    full_analysis = ""
    for i, (mention, evaluation) in enumerate(zip(mentions, evaluations), start=1):
        thread_summary = await mention.to_prompt_summary()
        tweet_analysis = str(evaluation).rstrip() + "\n\n"
        full_analysis += "\n".join([SECTION_DIVIDER, f"Tweet #{i}:", thread_summary, tweet_analysis])

    # Build the prompt section:
    #
    # --------------------
    # Prompt:
    #
    #   def get_reply_guy...
    prompt_source_code = get_prompt_source_code(agent_profile)
    prompt_section = f"{SECTION_DIVIDER}\nPrompt:\n\n{prompt_source_code}\n"

    # Put it all together
    output = f"{header}{responses_summary}{full_analysis}{prompt_section}"
    with open(output_file, "w") as f:
        f.write(output)


async def generate_tweet_responses(tweets_file):
    """
    Main testing function to generate a reply guy response for the configured given agent profile,
    based on a fixed sample of tweets - used to help tune the prompt
    """
    current_time = datetime.datetime.now().isoformat(timespec="seconds")
    current_time_in_file = current_time.replace(":", "-").replace("T", "_")
    output_file = OUTPUT_DIRECTORY / f"{current_time_in_file}.txt"

    # Get the agent profile
    agent_profile = profiles.get_agent_profile()

    # Read the raw tweet examples
    with open(INPUT_DIRECTORY / tweets_file, "r") as f:
        raw_mentions = json.loads(f.read())

    # Create the output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIRECTORY):
        os.mkdir(OUTPUT_DIRECTORY)

    # Build back the list of mentions from the JSON
    mentions = [TweetMention.from_dict(mention) for mention in raw_mentions]

    # Generate the response to each mention
    evaluations = []
    for mention in mentions:
        try:
            evaluation = await get_response(agent_profile=agent_profile, mention=mention)
        except Exception as e:
            evaluation = TweetEvaluation(
                response="Error occurred",
                tweet_analysis=str(e),
                engagement_strategy="N/A",
                response_rating=0,
                meme_name="N/A",
                meme_id=-1,
                meme_caption="N/A",
                meme_rating=0,
            )
        evaluations.append(evaluation)

    # Write the responses to an output file
    await write_output_file(
        agent_profile=agent_profile,
        current_time=current_time,
        output_file=output_file,
        mentions=mentions,
        evaluations=evaluations,
    )
