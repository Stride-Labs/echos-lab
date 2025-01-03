from requests_oauthlib import OAuth1Session

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env_or_raise


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
