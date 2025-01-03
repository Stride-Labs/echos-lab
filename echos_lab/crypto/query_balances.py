from typing import Dict, List

import echos_lab.crypto.crypto_helpers as ch
from echos_lab.crypto import goldsky, uniswap_pricing


def get_erc20_balance(address, token_address) -> int:
    token_contract = ch.web3.eth.contract(
        address=ch.web3.to_checksum_address(token_address),
        abi=ch.abis.erc20_abi,
    )
    balance = token_contract.functions.balanceOf(ch.web3.to_checksum_address(address)).call()
    return balance


def get_price(address: str) -> float:
    result = goldsky.client.execute(goldsky.METADATA_QUERY, variable_values={"id": address})
    return float(result['memeToken']['marketData']['currentPrice'])


def get_balances(address: str) -> List[Dict]:
    response = goldsky.client.execute(goldsky.BALANCE_QUERY, variable_values={"address": address})
    balances = response['accountTokenBalances']
    out = []
    for balance in balances:
        token = balance['token']
        is_graduated = token['marketData']['graduated']
        if is_graduated:
            price = uniswap_pricing.get_asset_price(token['id'])
            amount = int(get_erc20_balance(address, token['id'])) / ch.ONE_BASE_TOKEN
            balance_usd = amount * price
            market_cap = price * 1_000_000_000
        else:
            amount = int(balance['balance']) / ch.ONE_BASE_TOKEN
            balance_usd = amount * float(token['marketData']['currentPrice'])
            market_cap = int(token['marketData']['marketCap']) / ch.ONE_BASE_TOKEN
        # filter out tokens with too much or too little value
        if (balance_usd > 1_000_000) or (balance_usd < 0.5):
            continue
        if market_cap > 1_000_000_000:
            continue
        out.append(
            {
                "symbol": token['symbol'],
                "name": token['name'],
                "balance": amount,
                "balanceUSD": balance_usd,
                "marketCap": market_cap,
                "address": token['id'],
            }
        )
    # now grab USDC balance
    balance_usdc = ch.web3.eth.get_balance(ch.web3.to_checksum_address(address)) / ch.ONE_BASE_TOKEN
    out.append(
        {
            "symbol": ch.BASE_ASSET,
            "name": ch.BASE_ASSET_NAME,
            "balance": balance_usdc,
            "balanceUSD": balance_usdc,
            "marketCap": 100_000_000_000,
            "volume": 100_000_000_000,
            "address": ch.BASE_ASSET,
        }
    )
    # sort out by balance USD
    out = sorted(out, key=lambda x: x['balanceUSD'], reverse=True)
    return out
