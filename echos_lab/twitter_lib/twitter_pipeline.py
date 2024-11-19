from sqlalchemy.orm import Session
from echos_lab.engines import post_retriever
from twitter.account import Account
from twitter.scraper import Scraper
from echos_lab.db.models import TweetPost
from typing import List, Dict


def get_recent_tweets(
    db: Session, account: Account, scraper: Scraper, notifications_only=False
) -> tuple[List[Dict], str, List[tuple[str, str]]]:
    '''
    Gets the most recent tweets on the timeline
    '''
    if notifications_only:
        recent_posts = []
        formatted_recent_posts = ""
    else:
        # Step 1: Retrieve recent posts
        recent_posts = post_retriever.retrieve_recent_posts(db)
        formatted_recent_posts = post_retriever.format_post_list(recent_posts)
        print(f"Recent posts: {formatted_recent_posts}")

    # Step 2: Fetch external context
    notif_context_tuple = post_retriever.fetch_notification_context(
        account=account, scraper=scraper, notifications_only=notifications_only
    )

    return (recent_posts, formatted_recent_posts, notif_context_tuple)


def update_db_with_tweet_ids(db: Session, notif_context_tuple: List[tuple[str, str]]):
    '''
    Adds tweet ids to the database, returns a filtered list of tweet ids that haven't been seen before
    '''
    notif_context_id = [context[1] for context in notif_context_tuple]

    # filter all of the notifications for ones that haven't been seen before
    existing_tweet_ids = {tweet.tweet_id for tweet in db.query(TweetPost.tweet_id).all()}
    filtered_notif_context_tuple = [context for context in notif_context_tuple if context[1] not in existing_tweet_ids]

    # add to database every tweet id you have seen
    for id in notif_context_id:
        new_tweet_post = TweetPost(tweet_id=id)
        db.add(new_tweet_post)
        db.commit()

    return filtered_notif_context_tuple
