import sys
import time
import undetected_chromedriver as uc
from selenium.webdriver import ChromeOptions, Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
import os
from dotenv import load_dotenv
import traceback
import json
from functools import lru_cache
from twitter.account import Account
from twitter.scraper import Scraper
from echos_lab.twitter_lib import twitter_helpers
from multiprocessing import freeze_support

freeze_support()

# link to _this_file
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
load_dotenv(f"{BASE_PATH}/../.env")

TWITTER_ACCOUNT = os.getenv("TWITTER_ACCOUNT", "")
if TWITTER_ACCOUNT == "":
    raise ValueError("TWITTER_ACCOUNT not found in .env file")

PASSWORD = os.getenv("TWITTER_PASSWORD", "")
if PASSWORD == "":
    raise ValueError("TWITTER_PASSWORD not found in .env file")
X_EMAIL = os.getenv("X_EMAIL", "")
if X_EMAIL == "":
    raise ValueError("X_EMAIL not found in .env file")

AUTH_TOKEN = ""
MAX_WORKERS = 2

LAST_LOGIN_TIME = time.time()
WAIT_TO_LOGIN = 60 * 30  # wait 30m

options = ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--no-sandbox')
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

driver = None


@lru_cache
def get_twitter_account() -> Account:
    auth_tokens = twitter_helpers.load_cookies_json()
    account = Account(cookies=auth_tokens)
    return account


@lru_cache
def get_twitter_scraper() -> Scraper:
    auth_tokens = twitter_helpers.load_cookies_json()
    scraper = Scraper(cookies=auth_tokens)
    return scraper


# define global functions, to be pickled and run in a separate process
def get_user_id_target(username):
    scraper = get_twitter_scraper()
    return scraper.users([username])


def get_user_posts_target(user_id):
    scraper = get_twitter_scraper()
    return scraper.tweets([user_id])[0]


def get_driver():
    global driver
    global options
    if driver is None:
        driver = uc.Chrome(
            options=options,
            headless=True,
            version_main=131,
            use_subprocess=False,
        )
    return driver


def get_cookies_from_driver():
    global driver
    driver = get_driver()
    ct0 = driver.get_cookie("ct0")
    if not ct0:
        raise ValueError("ct0 cookie not found")
    ct0 = ct0["value"]
    auth_token = driver.get_cookie("auth_token")
    if not auth_token:
        raise ValueError("auth_token cookie not found")
    auth_token = auth_token["value"]

    # Get bearer token from network requests
    bearer_token = None
    logs = driver.get_log('performance')
    for log in logs:
        if 'message' in log and 'message' in log['message']:
            message = json.loads(log['message'])
            if 'message' in message and 'params' in message['message'] and 'request' in message['message']['params']:
                request = message['message']['params']['request']
                if (
                    'headers' in request
                    and 'authorization' in request['headers']
                    and request['headers']['authorization'].startswith('Bearer ')
                ):
                    bearer_token = request['headers']['authorization'].split('Bearer ')[1]
                    break
    if not bearer_token:
        raise ValueError("Bearer token not found")

    cookies = dict(ct0=ct0, auth_token=auth_token, bearer_token=bearer_token)
    return cookies


def login_to_twitter() -> None:
    global AUTH_TOKEN
    global LAST_LOGIN_TIME
    global driver
    LAST_LOGIN_TIME = time.time()

    url = "https://twitter.com/i/flow/login"
    driver = get_driver()
    driver.get(url)

    username = WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
    )
    username.send_keys(TWITTER_ACCOUNT)
    username.send_keys(Keys.ENTER)
    print('sent twitter account', file=sys.stderr)
    time.sleep(1)

    input_field = WebDriverWait(driver, 10).until(
        EC.any_of(
            EC.visibility_of_element_located(((By.CSS_SELECTOR, 'input[name="password"]'))),
            EC.visibility_of_element_located(((By.CSS_SELECTOR, 'input[autocomplete="on"]'))),
        )
    )

    if input_field.get_attribute('autocomplete') == 'on':
        # Handle email field
        print("Found email field", sys.stderr)
        input_field.send_keys(X_EMAIL)
        input_field.send_keys(Keys.ENTER)
        time.sleep(1)

        input_field = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="current-password"]'))
        )

    print('password', file=sys.stderr)
    input_field.send_keys(PASSWORD)
    input_field.send_keys(Keys.ENTER)

    time.sleep(5)
    cookies = get_cookies_from_driver()
    AUTH_TOKEN = cookies['auth_token']
    twitter_helpers.write_cookies(cookies)

    print('waiting for driver', file=sys.stderr)

    try:
        allow_button = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[id="allow"]'))
        )
        allow_button.click()
    except Exception as e:
        print(e)


def post_tweet(tweet_contents: str, quote_tweet_id: str = "", reply_tweet_id: str = "") -> str:
    account = get_twitter_account()
    if quote_tweet_id != "":
        tweet_obj = account.quote(tweet_contents, int(quote_tweet_id))
    elif reply_tweet_id != "":
        tweet_obj = account.reply(tweet_contents, int(reply_tweet_id))
    else:
        tweet_obj = account.tweet(tweet_contents)
    print("TWEET ATTEMPTED")
    print(tweet_obj)
    try:
        tweet_result = tweet_obj['data']['create_tweet']['tweet_results']['result']
        tweet_id = tweet_result['rest_id']
        username = tweet_result['core']['user_results']['result']['legacy']['screen_name']
        url = f"https://twitter.com/{username}/status/{tweet_id}"
        return url
    except Exception:
        return ""


@lru_cache
def get_tweet_by_id(id: str, scraper: Scraper) -> dict:
    time.sleep(2)
    try:
        tweet_raw = scraper.tweets_by_id([id])[0]['data']['tweetResult']['result']
        out = tweet_raw['legacy']
        out['screen_name'] = tweet_raw['core']['user_results']['result']['legacy']['screen_name']
        return out
    except Exception:
        print(f"ERROR GETTING TWEET {id}")
        traceback.print_exc()
        if time.time() - LAST_LOGIN_TIME > WAIT_TO_LOGIN:
            login_to_twitter()
        return {}


@lru_cache
def get_user_id(username: str):
    users = get_user_id_target(username)

    # process the result as usual
    if users:
        return users[0]['data']['user']['result']['rest_id']
    else:
        return None


def get_tweets_from_user(username: str) -> str:
    user_id = get_user_id(username)
    tweets = get_user_posts_target(user_id)
    output_text = f"LIST OF TWEETS FROM {username}\n"
    try:
        all_instructions = tweets['data']['user']['result']['timeline_v2']['timeline']['instructions']
        relevant_instruction = None
        for i in range(len(all_instructions)):
            if 'entries' in all_instructions[i]:
                relevant_instruction = all_instructions[i]
                break
        if not relevant_instruction:
            return "No tweets found"
        for tweet in relevant_instruction['entries']:
            tweet_user = tweet['content']['itemContent']['tweet_results']['result']['legacy']['user_id_str']
            if tweet_user != user_id:
                continue
            tweet_text = tweet['content']['itemContent']['tweet_results']['result']['legacy']['full_text']
            tweet_id = tweet['content']['itemContent']['tweet_results']['result']['legacy']['id_str']
            output_text += f"\t{tweet_text}\n\tTweet ID: {tweet_id}\n"
        output_text += f"END OF TWEETS FROM {username}\n"
    except Exception:
        output_text = "Error: Could not retrieve tweets"

    return output_text


if __name__ == "__main__":
    login_to_twitter()
