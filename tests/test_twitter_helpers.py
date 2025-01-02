from conftest import build_tweet

from echos_lab.twitter import twitter_helpers
from echos_lab.twitter.types import TweetExclusions


class TestFilterTweetExclusions:
    def test_filter_tweet_exclusions_no_exclusions(self):
        """
        Tests calling filter tweet exclusions with no exclusions
        """
        tweets = [
            build_tweet(1, "tweet", conversation_id=1),
            build_tweet(2, "tweet", conversation_id=2),
            build_tweet(3, "tweet", conversation_id=2, reference_id=4, reference_type="replied_to"),
        ]
        assert twitter_helpers.filter_tweet_exclusions(tweets=tweets, exclusions=[]) == tweets
        assert twitter_helpers.filter_tweet_exclusions(tweets=[], exclusions=[]) == []

    def test_filter_tweet_exclusions_exclude_replies(self):
        """
        Tests calling filter tweet exclusions while excluding direct replies
        """
        excluded_ids = [3, 9]
        input_tweets = [
            build_tweet(0, "tweet"),
            build_tweet(1, "tweet"),
            build_tweet(2, "tweet", reference_id=10, reference_type="quoted"),
            build_tweet(3, "tweet", reference_id=10, reference_type="replied_to"),
            build_tweet(4, "tweet", reference_id=10, reference_type="quoted"),
            build_tweet(5, "tweet", reference_id=10, reference_type="retweeted"),
            build_tweet(6, "tweet"),
            build_tweet(7, "tweet", reference_id=10, reference_type="retweeted"),
            build_tweet(8, "tweet", reference_id=10, reference_type="quoted"),
            build_tweet(9, "tweet", reference_id=10, reference_type="replied_to"),
        ]
        expected_tweets = [tweet for tweet in input_tweets if tweet.id not in excluded_ids]
        actual_tweets = twitter_helpers.filter_tweet_exclusions(
            tweets=input_tweets, exclusions=[TweetExclusions.REPLIES]
        )
        assert expected_tweets == actual_tweets

    def test_filter_tweet_exclusions_exclude_quotes(self):
        """
        Tests calling filter tweet exclusions while excluding quote tweets
        """
        excluded_ids = [2, 4, 8]
        input_tweets = [
            build_tweet(0, "tweet"),
            build_tweet(1, "tweet"),
            build_tweet(2, "tweet", reference_id=10, reference_type="quoted"),
            build_tweet(3, "tweet", reference_id=10, reference_type="replied_to"),
            build_tweet(4, "tweet", reference_id=10, reference_type="quoted"),
            build_tweet(5, "tweet", reference_id=10, reference_type="retweeted"),
            build_tweet(6, "tweet"),
            build_tweet(7, "tweet", reference_id=10, reference_type="retweeted"),
            build_tweet(8, "tweet", reference_id=10, reference_type="quoted"),
            build_tweet(9, "tweet", reference_id=10, reference_type="replied_to"),
        ]
        expected_tweets = [tweet for tweet in input_tweets if tweet.id not in excluded_ids]
        actual_tweets = twitter_helpers.filter_tweet_exclusions(
            tweets=input_tweets, exclusions=[TweetExclusions.QUOTE_TWEETS]
        )
        assert expected_tweets == actual_tweets

    def test_filter_tweet_exclusions_exclude_retweets(self):
        """
        Tests calling filter tweet exclusions while excluding retweets
        """
        excluded_ids = [5, 7]
        input_tweets = [
            build_tweet(0, "tweet"),
            build_tweet(1, "tweet"),
            build_tweet(2, "tweet", reference_id=10, reference_type="quoted"),
            build_tweet(3, "tweet", reference_id=10, reference_type="replied_to"),
            build_tweet(4, "tweet", reference_id=10, reference_type="quoted"),
            build_tweet(5, "tweet", reference_id=10, reference_type="retweeted"),
            build_tweet(6, "tweet"),
            build_tweet(7, "tweet", reference_id=10, reference_type="retweeted"),
            build_tweet(8, "tweet", reference_id=10, reference_type="quoted"),
            build_tweet(9, "tweet", reference_id=10, reference_type="replied_to"),
        ]
        expected_tweets = [tweet for tweet in input_tweets if tweet.id not in excluded_ids]
        actual_tweets = twitter_helpers.filter_tweet_exclusions(
            tweets=input_tweets, exclusions=[TweetExclusions.RETWEETS]
        )
        assert expected_tweets == actual_tweets
