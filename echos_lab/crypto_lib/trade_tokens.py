from typing import cast

from eth_account.signers.local import LocalAccount
from web3.types import Nonce, Wei

from echos_lab.crypto_lib import abis
from echos_lab.crypto_lib import crypto_helpers as ch
from echos_lab.crypto_lib import goldsky


def trade_pregrad_token(
    is_buy: bool,
    token_address: str,
    human_readable_amount: int,
    account: LocalAccount,
    min_amount_received: int = 0,
) -> bool:
    """
    Will buy or sell the pre-grad token
    If you want to buy, you must pass "is_buy=True"
    If you want to sell, you must pass "is_buy=False"

    "human_readable_amount" will be the regular token amount, not the uToken amount.

    E.g.  trade_pregrad_token(True, "0x...", 50) will buy 50 USDC of token

    Will return True if the tx succeeded, False otherwise
    """
    factory_contract = ch.web3.eth.contract(
        address=ch.web3.to_checksum_address(ch.ECHO_MANAGER_ADDRESS),
        abi=abis.meme_manager_abi,
    )
    trade_amount = int(human_readable_amount * ch.ONE_BASE_TOKEN)
    trade_params = {
        "from": account.address,
        "nonce": ch.web3.eth.get_transaction_count(account.address),
        "gas": 7_000_000,
        "gasPrice": ch.GAS_PRICE,
        "chainId": ch.ECHOS_CHAIN_ID,
    }
    if is_buy:
        factory_function = factory_contract.functions.buy(token_address, trade_amount, min_amount_received)
        trade_params["value"] = trade_amount
    else:
        factory_function = factory_contract.functions.sell(token_address, trade_amount, min_amount_received)
    direct_tx = factory_function.build_transaction(trade_params)  # type: ignore
    receipt = ch.sign_and_send_tx(account, direct_tx)
    if receipt.get('status') == 1:
        return True
    else:
        print("Token purchase failed")
        print(f"Full receipt: {receipt}")
        return False


def buy_pregrad_token(
    token_address: str,
    human_readable_amount: int,
    account: LocalAccount,
    min_amount_received: int = 0,
) -> bool:
    return trade_pregrad_token(True, token_address, human_readable_amount, account, min_amount_received)


def sell_pregrad_token(
    token_address: str,
    human_readable_amount: int,
    account: LocalAccount,
    min_amount_received: int = 0,
) -> bool:
    return trade_pregrad_token(True, token_address, human_readable_amount, account, min_amount_received)


def trade_univ3(
    from_token_address: str,
    to_token_address: str,
    human_readable_in_amount: int,
    account: LocalAccount,
    min_amount_received: int = 0,
    fee: int = 2500,
) -> bool:
    """
    Executes a trade on uniswap
    """
    # Step 1: convert to wrapped USDC if needed
    final_token_in = ch.WUSDC_ADDRESS if from_token_address == "USDC" else from_token_address
    final_token_out = ch.WUSDC_ADDRESS if to_token_address == "USDC" else to_token_address
    metadata = ch.get_token_metadata(final_token_in)
    trade_amount = int(human_readable_in_amount * (10 ** metadata['decimals']))

    # Step 2: get the pool address
    factory_contract = ch.web3.eth.contract(
        address=ch.web3.to_checksum_address(ch.UNISWAP_FACTORY_ADDRESS),
        abi=abis.uniswap_factory_abi,
    )
    pool_address = factory_contract.functions.getPool(final_token_in, final_token_out, fee).call()
    if pool_address == ch.ZERO_ADDRESS:
        raise ValueError("Pool does not exist for the provided tokens and fee.")

    # Step 3: get the router contract, construct params
    router_contract = ch.web3.eth.contract(
        address=ch.web3.to_checksum_address(ch.UNISWAP_ROUTER_ADDRESS),
        abi=abis.uniswap_router_abi,
    )
    trade_params = {
        "from": account.address,
        "nonce": ch.web3.eth.get_transaction_count(account.address),
        "gas": 7_000_000,
        "gasPrice": ch.GAS_PRICE,
        "chainId": ch.ECHOS_CHAIN_ID,
    }
    if from_token_address == ch.BASE_ASSET:
        # trading from USDC -> MEME
        final_trade_function = router_contract.functions.exactInputSingle(
            (final_token_in, final_token_out, fee, account.address, trade_amount, min_amount_received, 0)
        )
        trade_params["value"] = Wei(trade_amount)  # explicit conversion to Wei
    elif to_token_address == ch.BASE_ASSET:
        # trading from MEME -> USDC
        # first grant approval
        ch.approve_token_spending(account, final_token_in, router_contract.address, trade_amount)
        current_nonce = int(cast(Nonce, trade_params["nonce"]))
        trade_params["nonce"] = Nonce(current_nonce + 1)
        # now build the two subcalls
        trade_function = router_contract.functions.exactInputSingle(
            (final_token_in, final_token_out, fee, router_contract.address, trade_amount, min_amount_received, 0)
        )._encode_transaction_data()
        unwrap_function = router_contract.functions.unwrapWETH9(0, account.address)._encode_transaction_data()
        # Build multicall transaction
        final_trade_function = router_contract.functions.multicall([trade_function, unwrap_function])
    else:
        ch.approve_token_spending(account, final_token_in, router_contract.address, trade_amount)
        current_nonce = int(cast(Nonce, trade_params["nonce"]))
        trade_params["nonce"] = Nonce(current_nonce + 1)
        final_trade_function = router_contract.functions.exactInputSingle(
            final_token_in, final_token_out, fee, account.address, trade_amount, min_amount_received, 0
        )
    direct_tx = final_trade_function.build_transaction(trade_params)  # type: ignore
    receipt = ch.sign_and_send_tx(account, direct_tx)
    return receipt.get('status') == 1


def get_if_token_graduated(token_address: str) -> bool:
    """
    Returns True if the token has graduated, False otherwise
    """
    result = goldsky.client.execute(goldsky.METADATA_QUERY, variable_values={"id": token_address})
    return result['memeToken']['marketData']['graduated']


def trade_token(from_token_address, to_token_address, human_readable_in_amount, account, min_amount_received=0) -> bool:
    if from_token_address == to_token_address:
        print("Cannot trade a token for itself")
        return False
    if from_token_address == 'USDC':
        is_graduated = get_if_token_graduated(to_token_address)
    elif to_token_address == 'USDC':
        is_graduated = get_if_token_graduated(from_token_address)
    else:
        print("Cannot trade between two non-USDC tokens")
        return False
    if is_graduated:
        return trade_univ3(from_token_address, to_token_address, human_readable_in_amount, account, min_amount_received)
    else:
        if from_token_address == 'USDC':
            return trade_pregrad_token(True, to_token_address, human_readable_in_amount, account, min_amount_received)
        else:
            return trade_pregrad_token(
                False, from_token_address, human_readable_in_amount, account, min_amount_received
            )
