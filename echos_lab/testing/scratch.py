from typing import cast

from tweepy import Response

from echos_lab.twitter import twitter_auth


async def post_tweet(client, tweet="Hello world."):
    try:
        response = await client.create_tweet(text=tweet)
        print("Tweet successfully posted!")
        print("Tweet ID:", response.data['id'])
    except Exception as e:
        print("Error while tweeting:", e)


async def test_tweet():
    client = twitter_auth.get_tweepy_async_client()
    await post_tweet(client)


async def test_get_follower_count(user_id) -> int:
    client = twitter_auth.get_tweepy_async_client()
    response = await client.get_user(id=user_id, user_fields="public_metrics")
    response = cast(Response, response)
    if not response or not response.data:
        return False

    user = response.data
    if not hasattr(user, "public_metrics") or not user.public_metrics:
        return False

    print(f"User ID: {user.id}, Followers: {user.public_metrics['followers_count']}")
    return user.public_metrics["followers_count"]


async def main():
    await test_tweet()
    await test_get_follower_count(1506633322415411210)
