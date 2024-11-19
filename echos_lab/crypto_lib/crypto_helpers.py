from web3 import Web3
import os
from web3.types import TxParams, TxReceipt
from eth_account.signers.local import LocalAccount
from functools import lru_cache
from typing import Dict
from dotenv import load_dotenv
from echos_lab.crypto_lib import abis

# get path to _this_ file
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
load_dotenv(f"{BASE_PATH}/../.env")


ACCOUNT_PATH = os.getenv("CRYPTO_ACCOUNT_PATH", "")
if ACCOUNT_PATH == "":
    ACCOUNT_PATH = f"{BASE_PATH}/account.json"

CHAIN_ID = int(os.getenv("CHAIN_ID", "1"))
if CHAIN_ID == 1:
    raise ValueError("CHAIN_ID not found in .env file")

CHAIN_RPC = os.getenv("CHAIN_RPC", "")
if CHAIN_RPC == "":
    raise ValueError("CHAIN_RPC not found in .env file")

TOKEN_FACTORY_ADDRESS = os.getenv("TOKEN_FACTORY_ADDRESS", "")
if TOKEN_FACTORY_ADDRESS == "":
    raise ValueError("TOKEN_FACTORY_ADDRESS not found in .env file")

UNISWAP_ROUTER_ADDRESS = os.getenv("UNISWAP_ROUTER_ADDRESS", "")
if UNISWAP_ROUTER_ADDRESS == "":
    raise ValueError("UNISWAP_ROUTER_ADDRESS not found in .env file")

UNISWAP_FACTORY_ADDRESS = os.getenv("UNISWAP_FACTORY_ADDRESS", "")
if UNISWAP_FACTORY_ADDRESS == "":
    raise ValueError("UNISWAP_FACTORY_ADDRESS not found in .env file")

WUSDC = os.getenv("WUSDC_ADDRESS", "")
if WUSDC == "":
    raise ValueError("WUSDC_ADDRESS not found in .env file")

PRIVATE_KEY_PASSWORD = os.getenv("PRIVATE_KEY_PASSWORD", "")
if PRIVATE_KEY_PASSWORD == "":
    raise ValueError("PRIVATE_KEY_PASSWORD not found in .env file")

# PRIVATE KEY OF BOT, in case we want to recover an account
BOT_PK = os.getenv("BOT_PK", "")

BASE_ASSET = "USDC"
BASE_ASSET_NAME = "USD Coin"
BASE_DECIMALS = 18
BASE_PRICE = 1.0

GAS_PRICE = Web3.to_wei(0.3, "gwei")

ONE_BASE_TOKEN = 10**BASE_DECIMALS

INITIAL_BUY = 10 * ONE_BASE_TOKEN

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

web3 = Web3(Web3.HTTPProvider(CHAIN_RPC))

if not web3.is_connected():
    raise ValueError("Could not connect to chain RPC")

WUSDC_CHECKSUM = web3.to_checksum_address(WUSDC)


def sign_and_send_tx(account: LocalAccount, direct_tx: TxParams) -> TxReceipt:
    signed_tx = account.sign_transaction(direct_tx)  # type: ignore
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Direct transaction sent with hash: {tx_hash.hex()} . Waiting...")
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


@lru_cache
def get_token_metadata(token_address: str) -> Dict:
    if token_address == BASE_ASSET:
        return {"name": BASE_ASSET_NAME, "symbol": BASE_ASSET, "decimals": BASE_DECIMALS}
    contract = web3.eth.contract(address=web3.to_checksum_address(token_address), abi=abis.erc20_abi)
    token_metadata = {
        "name": contract.functions.name().call(),
        "symbol": contract.functions.symbol().call(),
        "decimals": contract.functions.decimals().call(),
    }

    return token_metadata


def approve_token_spending(account: LocalAccount, token_address: str, spender_address: str, amount: int) -> bool:
    """Approve a contract to spend tokens on behalf of the user.

    Args:
        account: The account that will approve the spending
        token_address: Address of the ERC20 token contract
        spender_address: Address of the contract that will spend the tokens
        amount: Amount of tokens to approve (in smallest denomination)

    Returns:
        bool: True if approval succeeded, False otherwise
    """
    token_contract = web3.eth.contract(address=web3.to_checksum_address(token_address), abi=abis.erc20_abi)

    transaction = token_contract.functions.approve(web3.to_checksum_address(spender_address), amount).build_transaction(
        {
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address),
            "gas": 100_000,  # Standard gas limit for approvals
            "gasPrice": GAS_PRICE,
            "chainId": CHAIN_ID,
        }
    )

    signed_tx = account.sign_transaction(transaction)  # type: ignore
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Approval transaction sent with hash: {tx_hash.hex()} . Waiting...")

    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.get('status') == 1:
        print("Approval transaction succeeded")
        return True
    else:
        print("Approval transaction failed")
        return False
