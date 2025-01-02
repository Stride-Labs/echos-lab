from functools import lru_cache
from pathlib import Path
from typing import Dict

from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.types import TxParams, TxReceipt

from echos_lab.common.env import ECHOS_HOME_DIRECTORY
from echos_lab.common.env import EnvironmentVariables as envs
from echos_lab.common.env import get_env
from echos_lab.crypto_lib import abis

# w3 ETH Account Config
ACCOUNT_PATH = Path(get_env(envs.CRYPTO_ACCOUNT_PATH, ECHOS_HOME_DIRECTORY / "account.json"))
PRIVATE_KEY_PASSWORD = get_env(envs.CRYPTO_PRIVATE_KEY_PASSWORD, "password")

# Private key is only needed if recovering an account
PRIVATE_KEY = get_env(envs.CRYPTO_PRIVATE_KEY)

# Echos Chain Config
ECHOS_CHAIN_ID = int(get_env(envs.ECHOS_CHAIN_ID, "4321"))
ECHOS_CHAIN_RPC = get_env(envs.ECHOS_CHAIN_RPC, "https://rpc-echos-mainnet-0.t.conduit.xyz")

# Echos Contracts
ECHO_MANAGER_ADDRESS = get_env(envs.ECHOS_MANAGER_ADDRESS, "0x136BE3E45bBCc568F4Ec0bd47d58C799e7d1ae23")
UNISWAP_ROUTER_ADDRESS = get_env(envs.ECHOS_UNISWAP_ROUTER_ADDRESS, "0x5190f096B204C051fcc561363E8DbE023FA0119f")
UNISWAP_FACTORY_ADDRESS = get_env(envs.ECHOS_UNISWAP_FACTORY_ADDRESS, "0x17d70B17c3228f864D45eB964b2EDAB078106328")
WUSDC_ADDRESS = get_env(envs.ECHOS_WUSDC_ADDRESS, "0x37234506262FF64d97694eA1F0461414c9e8A39e")

# Gas Config
BASE_ASSET = "USDC"
BASE_ASSET_NAME = "USD Coin"
BASE_DECIMALS = 18
BASE_PRICE = 1.0
GAS_PRICE = Web3.to_wei(0.3, "gwei")
ONE_BASE_TOKEN = 10**BASE_DECIMALS

# Misc Config
INITIAL_BUY = 10 * ONE_BASE_TOKEN
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

web3 = Web3(Web3.HTTPProvider(ECHOS_CHAIN_RPC))

if not web3.is_connected():
    raise ValueError("Could not connect to chain RPC")


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
            "chainId": ECHOS_CHAIN_ID,
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
