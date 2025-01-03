from requests_oauthlib import OAuth1Session

from tweepy import API, OAuth1UserHandler
from tweepy.asynchronous import AsyncClient
from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env_or_raise

# Module level singleton to store tweepy client
_tweepy_async_client: AsyncClient | None = None
_tweepy_oauth1_client: API | None = None


def get_tweepy_async_client():
    """
    Singleton to get or create the tweepy client
    """
    consumer_key = get_env_or_raise(envs.TWITTER_CONSUMER_KEY)
    consumer_secret = get_env_or_raise(envs.TWITTER_CONSUMER_SECRET)
    access_token = get_env_or_raise(envs.TWITTER_ACCESS_TOKEN)
    access_token_secret = get_env_or_raise(envs.TWITTER_ACCESS_TOKEN_SECRET)
    bearer_token = get_env_or_raise(envs.TWITTER_BEARER_TOKEN)

    global _tweepy_async_client

    if not _tweepy_async_client:
        _tweepy_async_client = AsyncClient(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            bearer_token=bearer_token,
            wait_on_rate_limit=True,
        )
    return _tweepy_async_client


def get_tweepy_oauth1_client():
    """
    Creates a new Tweepy API instance
    """
    consumer_key = get_env_or_raise(envs.TWITTER_CONSUMER_KEY)
    consumer_secret = get_env_or_raise(envs.TWITTER_CONSUMER_SECRET)
    access_token = get_env_or_raise(envs.TWITTER_ACCESS_TOKEN)
    access_token_secret = get_env_or_raise(envs.TWITTER_ACCESS_TOKEN_SECRET)

    global _tweepy_oauth1_client

    if not _tweepy_oauth1_client:
        auth = OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
        _tweepy_oauth1_client = API(auth)

    return _tweepy_oauth1_client


def get_twitter_access_tokens():
    """
    This function will guide you through the process of obtaining the access
    tokens for a Twitter app. It will print a URL that you must visit to
    authorize the app, and then ask you to paste the PIN that Twitter gives
    you back into the console. It will then print the access tokens.
    """
    # Replace these with your app's consumer key and secret
    CONSUMER_KEY = get_env_or_raise(envs.TWITTER_CONSUMER_KEY)
    CONSUMER_SECRET = get_env_or_raise(envs.TWITTER_CONSUMER_SECRET)

    # Step 1: Obtain request token
    request_token_url = "https://api.twitter.com/oauth/request_token"
    oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET, callback_uri="oob")
    fetch_response = oauth.fetch_request_token(request_token_url)
    resource_owner_key = fetch_response.get("oauth_token")
    resource_owner_secret = fetch_response.get("oauth_token_secret")

    # Step 2: Redirect user for authorization
    base_authorization_url = "https://api.twitter.com/oauth/authorize"
    authorization_url = oauth.authorization_url(base_authorization_url)
    print("Please go here and authorize:", authorization_url)

    # Step 3: Get the verifier code from the user
    verifier = input("Paste the PIN here: ")

    # Step 4: Obtain access token
    access_token_url = "https://api.twitter.com/oauth/access_token"
    oauth = OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=verifier,
    )
    oauth_tokens = oauth.fetch_access_token(access_token_url)
    access_token = oauth_tokens["oauth_token"]
    access_token_secret = oauth_tokens["oauth_token_secret"]

    print(f"access_token: {access_token}")
    print(f"access_token_secret: {access_token_secret}")

    return access_token, access_token_secret
