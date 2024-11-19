from echos_lab.twitter_lib import twitter_connector, twitter_helpers
from dotenv import load_dotenv


load_dotenv()


def login_to_twitter_if_needed():
    if twitter_helpers.are_cookies_stale():
        twitter_connector.login_to_twitter()


def main():
    login_to_twitter_if_needed()


if __name__ == "__main__":
    main()
