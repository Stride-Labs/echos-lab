import asyncio
import json
import time
from contextlib import contextmanager
from functools import partial

import pydash
import undetected_chromedriver as uc
from selenium.webdriver import ChromeOptions, Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from twitter.account import Account
from twitter.scraper import Scraper

from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env_or_raise
from echos_lab.common.logger import logger
from echos_lab.common.utils import async_cache
from echos_lab.twitter_lib import twitter_helpers

# TODO: Organize files into: twitter_client.py (tweepy) and twitter_scraper.py (headless)

# Module singleton storage for driver, account, and scraper
_driver: uc.Chrome | None = None
_account: Account | None = None
_scraper: Scraper | None = None
_cookie_auth_token: str | None = None

# Global login state
_last_login_time = time.time()
_login_frequency = 60 * 30  # wait 30m

# Chrome drive settings
options = ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--no-sandbox')
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})


@contextmanager
def driver_context(headless: bool = True):
    """Context manager for Chrome driver"""
    driver = None
    try:
        driver = get_driver(headless)
        yield driver
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# TODO: Consider encapsulating login/refresh code in a class
def get_driver(headless: bool = True) -> uc.Chrome:
    """
    Singleton to get or create the chrome driver
    """
    global _driver
    global options
    if _driver is None:
        if headless:
            # Trying these arguments for better headless support
            options.add_argument('--headless=new')  # Using the new headless mode
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--enable-javascript')
            options.add_argument("--disable-blink-features=AutomationControlled")

        _driver = uc.Chrome(
            options=options,
            headless=headless,
            version_main=131,
            use_subprocess=False,
        )

        # Set window size explicitly after creation
        if headless:
            user_agent = (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            )
            _driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
    return _driver


def get_twitter_account() -> Account:
    """
    Singleton to get or create the twitter account
    """
    global _account
    if _account is None:
        auth_tokens = twitter_helpers.load_cookies()
        _account = Account(cookies=auth_tokens)
    return _account


def get_twitter_scraper() -> Scraper:
    """
    Singleton to get or create the twitter scraper
    """
    global _scraper
    if _scraper is None:
        auth_tokens = twitter_helpers.load_cookies()
        _scraper = Scraper(cookies=auth_tokens)
    return _scraper


@async_cache()
async def get_user_id_from_username(username: str, scraper: Scraper | None = None) -> int | None:
    """
    Retrieves the user ID from the username

    The scraper logic must be run in it's own executor because it uses
    it's own event loop internally, which will clash with the main one

    Returns None if the username was not found
    """
    loop = asyncio.get_running_loop()
    scraper = scraper or get_twitter_scraper()
    response = await loop.run_in_executor(None, partial(scraper.users, [username]))
    return pydash.get(response, "[0].data.user.result.rest_id")


async def get_tweets_from_user_id(user_id: int, scraper: Scraper) -> list[tuple[str, str]]:
    """
    Retrieves the posts from a user, given their ID

    The scraper logic must be run in it's own executor because it uses
    it's own event loop internally, which will clash with the main one
    """
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, partial(scraper.tweets, [user_id]))
    return parse_tweets_from_scraped_response(response, user_id)


@async_cache()
async def get_tweet_from_tweet_id(id: str, scraper: Scraper) -> dict | None:
    """
    Retreives a tweet from the ID, returns None if it doesnt not exist

    The scraper logic must be run in it's own executor because it uses
    it's own event loop internally, which will clash with the main one
    """
    loop = asyncio.get_running_loop()
    await asyncio.sleep(2)  # TODO: Do we need this?

    response = await loop.run_in_executor(None, partial(scraper.tweets_by_id, [id]))
    result = pydash.get(response, "[0].data.tweetResult.result")
    if not result:
        login_to_twitter(force_refresh=True)  # handles failure from session timeout
        return None

    tweet = result["legacy"]
    screen_name = pydash.get(result, "core.user_results.result.legacy.screen_name", "Unknown")
    tweet["screen_name"] = screen_name

    return tweet


# TODO: Move somewhere else
def parse_tweets_from_scraped_response(response: list[dict], user_id: int) -> list[tuple[str, str]]:
    """
    Starting from the scraped API response for all tweets for a given user, extracts the
    the individual tweets and returns it as a list of (id, tweet_msg) tuples
    """
    # Grab the instructions section under timeline
    instructions = pydash.get(response, "[0].data.user.result.timeline_v2.instructions")
    if not instructions:
        logger.info("No tweet 'instructions' found on timeline query")
        return []

    # Find the instruction that has an "entries"
    relevant_instruction = next((instruction for instruction in instructions if "entries" in instruction), None)
    if not relevant_instruction:
        logger.info("No instruction with 'entries' in user tweets API response")
        return []

    # Loop through the "entries" and store the ID and contents of each tweet from the specified user
    tweets = []
    for tweet in relevant_instruction["entries"]:
        tweet_info = pydash.get(tweet, "content.itemContent.tweet_results.result.legacy")
        if not tweet_info:
            logger.error("Error: Could not retrieve tweet info from API response")
            continue

        tweeter = int(tweet_info["user_id_str"])
        if user_id != tweeter:
            continue

        tweets.append((tweet_info["id_str"], tweet_info["full_text"]))

    return tweets


def get_cookies_from_driver(driver: uc.Chrome) -> dict:
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


def should_login(force_refresh: bool) -> bool:
    """
    Checks whether we should login or relogin to twitter, based on the following:
     - If the cookies file doesn't exist, always login
     - If the cookies file is stale, always login
     - If the cookies file is not stale, and the login isn't forced, don't login
     - If the cookies file is stale, and the login is forced, only login if enough
       time has passed since the last login
    """
    # If the cookies file doesn't exist or is stale, always login
    cookies_stale = twitter_helpers.are_cookies_stale()
    if cookies_stale is None or cookies_stale:
        return True

    # Otherwise, check if the refresh is forced and enough time has passed
    return force_refresh and time.time() - _last_login_time > _login_frequency


def login_to_twitter(headless: bool = True, force_refresh: bool = False) -> None:
    """
    Logs into twitter using a headless driver and persists the cookies file locally
    This function can also be used to refresh the login

    By default, it will only login if the cookies are stale, but you can optionally
    force it to refresh - however, it will be guarded by ensuring that enough time has
    passed since the last login
    """
    global _cookie_auth_token
    global _last_login_time
    _last_login_time = time.time()

    if not should_login(force_refresh):
        return None

    twitter_account = get_env_or_raise(envs.TWITTER_ACCOUNT)
    twitter_password = get_env_or_raise(envs.TWITTER_PASSWORD)
    twitter_email = get_env_or_raise(envs.TWITTER_EMAIL)

    url = "https://twitter.com/i/flow/login"
    driver = get_driver(headless)
    with driver_context(headless) as driver:
        driver.get(url)

        username = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
        )
        username.send_keys(twitter_account)
        username.send_keys(Keys.ENTER)
        logger.debug('sent twitter account')
        time.sleep(1)

        input_field = WebDriverWait(driver, 10).until(
            EC.any_of(
                EC.visibility_of_element_located(((By.CSS_SELECTOR, 'input[name="password"]'))),
                EC.visibility_of_element_located(((By.CSS_SELECTOR, 'input[autocomplete="on"]'))),
            )
        )

        if input_field.get_attribute('autocomplete') == 'on':
            # Handle email field
            logger.debug("Found email field")
            input_field.send_keys(twitter_email)
            input_field.send_keys(Keys.ENTER)
            time.sleep(1)

            input_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="current-password"]'))
            )

        logger.debug('password')
        input_field.send_keys(twitter_password)
        input_field.send_keys(Keys.ENTER)

        time.sleep(5)
        cookies = get_cookies_from_driver(driver)
        _cookie_auth_token = cookies['auth_token']
        twitter_helpers.write_cookies(cookies)

        logger.info('Login successful')

        try:
            allow_button = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[id="allow"]'))
            )
            allow_button.click()
        except Exception as e:
            logger.error(str(e))


def refresh_twitter_login():
    """
    Checks if enough time has passed since the last login, and if so, log in again
    """
    if time.time() - _last_login_time > _login_frequency:
        login_to_twitter()


async def get_tweets_from_username(username: str) -> str:
    """
    Retries the list of tweets from a given username and outputs them to the console
    """
    scraper = get_twitter_scraper()

    user_id = await get_user_id_from_username(username, scraper)
    if not user_id:
        return f"User ID not found for username @{username}"

    tweets = await get_tweets_from_user_id(user_id, scraper)
    if not tweets:
        return "No tweets found"

    output_text = f"LIST OF TWEETS FROM {username}\n"
    output_text += "\n".join([f"\t{tweet_text}\n\tTweet ID: {tweet_id}\n" for (tweet_text, tweet_id) in tweets])
    output_text += f"END OF TWEETS FROM {username}\n"

    return output_text
