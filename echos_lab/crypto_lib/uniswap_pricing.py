import traceback
from functools import lru_cache

from web3 import Web3
from web3.contract import Contract

from echos_lab.crypto_lib import abis
from echos_lab.crypto_lib import crypto_helpers as ch

NULL_ADDRESS = "0x0000000000000000000000000000000000000000"

uni_factory_abi = [
    {
        "constant": True,
        "inputs": [
            {"name": "tokenA", "type": "address"},
            {"name": "tokenB", "type": "address"},
            {"name": "fee", "type": "uint24"},
        ],
        "name": "getPool",
        "outputs": [{"name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]


@lru_cache
def get_pool_contract(token_address: str) -> tuple[str, Contract]:
    """
    From a token's contract address, this returns the pool contract address
    on Uniswap v3.

    In particular, this gets the token address for the pool _paired against BASE asset_

    If there are multiple pools, will return the one with the most liquidity (defined as "most base asset")
    """
    factory_contract = ch.web3.eth.contract(
        address=ch.web3.to_checksum_address(ch.UNISWAP_FACTORY_ADDRESS),
        abi=abis.uniswap_factory_abi,
    )

    fee_tiers = [2500, 500, 3000, 10000]
    best_pool_address = NULL_ADDRESS
    best_pool_contract = ch.web3.eth.contract(ch.web3.to_checksum_address(NULL_ADDRESS), abi=abis.null_abi)
    best_base_reserves = 0
    token_checksum = Web3.to_checksum_address(token_address)
    for fee_tier in fee_tiers:
        wusdc_checksum = ch.web3.to_checksum_address(ch.WUSDC_ADDRESS)
        pool_address = factory_contract.functions.getPool(token_checksum, wusdc_checksum, fee_tier).call()
        if pool_address == NULL_ADDRESS:
            continue
        pool_contract = ch.web3.eth.contract(address=pool_address, abi=abis.uni_pool_abi)
        # get slot0 data and liquidity
        slot0 = pool_contract.functions.slot0().call()
        sqrt_price_x96 = slot0[0]
        liquidity = pool_contract.functions.liquidity().call()
        # calculate reserves
        reserve_base = liquidity * (2**96 / sqrt_price_x96) / 10**ch.BASE_DECIMALS
        if reserve_base > best_base_reserves:
            best_pool_address = pool_address
            best_pool_contract = pool_contract
            best_base_reserves = reserve_base
    print(f"Best pool address for {token_address} is {best_pool_address}")
    return best_pool_address, best_pool_contract


@lru_cache
def get_asset_price(token_address: str) -> float:
    """
    Returns the price of an asset in terms of ETH.
    """
    if token_address == ch.BASE_ASSET:
        return ch.BASE_PRICE
    try:
        _, pool_contract = get_pool_contract(token_address)
        slot0 = pool_contract.functions.slot0().call()
        sqrt_price_x96 = slot0[0]
        price_xyz_in_eth = (sqrt_price_x96 / (1 << 96)) ** 2
        # TODO - how to figure out which token is the base token?
        # For now, just return the minimum of the two, which will work until FDV > $1B
        return min(ch.BASE_PRICE / price_xyz_in_eth, price_xyz_in_eth / ch.BASE_PRICE)
    except Exception as e:
        traceback.print_exc()
        print(f"Error getting price for {token_address}: {e}. Defaulting to 0.")
        return 0.0
