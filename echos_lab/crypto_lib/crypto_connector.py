import json
from functools import lru_cache
from typing import Dict, List

from eth_account import Account
from eth_account.signers.local import LocalAccount
from millify import millify

from echos_lab.crypto_lib import crypto_helpers as ch
from echos_lab.crypto_lib import query_balances, trade_tokens


@lru_cache
def get_account() -> LocalAccount:
    if ch.ACCOUNT_PATH.exists():
        with open(ch.ACCOUNT_PATH, "r") as f:
            encrypted_acct = json.load(f)

        raw_account = Account.decrypt(encrypted_acct, ch.PRIVATE_KEY_PASSWORD)
        account = Account.from_key(raw_account)
        print(f"Found ETH account at {ch.ACCOUNT_PATH}!")
        print(f"Address is: {account.address}")
        return account

    print(f"No ETH account found! Creating {ch.ACCOUNT_PATH}...")
    account = Account.from_key(ch.PRIVATE_KEY) if ch.PRIVATE_KEY else Account.create()
    encrypted_acct = Account.encrypt(account._private_key, ch.PRIVATE_KEY_PASSWORD)

    with open(ch.ACCOUNT_PATH, "w") as file:
        json.dump(encrypted_acct, file)

    print("Created account with address:", account.address)
    return account


@lru_cache
def get_address() -> str:
    account = get_account()
    return account.address


def query_self_account_balance() -> List[Dict]:
    account = get_account()
    balances = query_balances.get_balances(account.address)
    return balances


def format_balances(balances, min_usd=0.5) -> str:
    formatted_balances = []
    for balance in balances:
        if float(balance['balanceUSD']) < min_usd:
            continue
        str_balance = millify(balance['balanceUSD'])
        mkt_cap = millify(balance['marketCap'])
        formatted_balance = f"\t${balance['symbol']} ({balance['name']}):\n"
        formatted_balance += f"\t\tyour holdings: ${str_balance}\n"
        formatted_balance += f"\t\tmarket cap: ${mkt_cap}\n"
        formatted_balance += f"\t\taddress: {balance['address']}\n"
        formatted_balances.append(formatted_balance)
    total_balance = sum([float(balance['balanceUSD']) for balance in balances])
    out_string = f"Total balance: ${total_balance:,.2f}\n" + "\n".join(formatted_balances)
    return out_string


def trade(from_address: str, to_address: str, dollar_amount: float) -> bool:
    dollar_amount = min(dollar_amount, 50)
    account = get_account()
    if from_address != "USDC":
        # convert dollar amount to token amount
        from_address = ch.web3.to_checksum_address(from_address)
        price = query_balances.get_price(from_address)
        token_amount = dollar_amount / price
    else:
        token_amount = dollar_amount
    if to_address != "USDC":
        to_address = ch.web3.to_checksum_address(to_address)
    return trade_tokens.trade_token(from_address, to_address, token_amount, account)


def display_account_balances():
    """
    Prints the address and account balances
    """
    account = get_account()
    print(format_balances(query_balances.get_balances(account.address)))
