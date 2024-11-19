import json
import os
import time

COOKIES_PATH = os.getenv("TWITTER_COOKIES_PATH", "")
if COOKIES_PATH == "":
    # get path to _this_ file
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    COOKIES_PATH = os.path.join(BASE_PATH, "cookies.env")

MAX_COOKIES_LENGTH = 48 * 60 * 60  # how long cookies last in seconds, e.g. 48 hours


def delete_cookies():
    if os.path.exists(COOKIES_PATH):
        os.remove(COOKIES_PATH)


def write_cookies(cookies: dict):
    with open(COOKIES_PATH, 'w') as f:
        j = json.dumps(cookies).replace('"', '\\"').replace(' ', '')
        f.write(f"X_AUTH_TOKENS={j}\n")


def get_cookies_age_old():
    '''
    Returns the age of the cookies file in seconds.
    '''
    if os.path.exists(COOKIES_PATH):
        return time.time() - os.path.getmtime(COOKIES_PATH)
    return MAX_COOKIES_LENGTH * 1000


def are_cookies_stale():
    '''
    Returns True if the cookies file is older than MAX_COOKIES_LENGTH.
    '''
    return get_cookies_age_old() > MAX_COOKIES_LENGTH


def load_cookies() -> tuple[str, str, str]:
    '''
    Returns the auth_token, ct0, and bearer_token from the cookies.env file.
    '''
    with open(COOKIES_PATH, 'r') as f:
        content = f.read()
        tokens = json.loads(content.split('=')[1].replace('\\\"', '"'))
        auth_token = tokens['auth_token']
        ct0 = tokens['ct0']
        bearer_token = tokens.get('bearer_token')
    return auth_token, ct0, bearer_token


def load_cookies_json() -> dict:
    '''
    Returns the auth_token, ct0, and bearer_token from the cookies.env file.
    '''
    with open(COOKIES_PATH, 'r') as f:
        content = f.read()
        tokens = json.loads(content.split('=')[1].replace('\\\"', '"'))
    return tokens
