from twitter.account import Account


def follow_user(account: Account, user_id):
    return account.follow(user_id)


def like_post(account: Account, post_id):
    return account.like(post_id)
