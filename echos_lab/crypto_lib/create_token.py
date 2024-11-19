from echos_lab.engines import image_creator, agent_interests
from echos_lab.crypto_lib import abis, query_balances
from echos_lab.crypto_lib import crypto_helpers as ch
from eth_account.signers.local import LocalAccount
import time


def try_creating_image(symbol: str, name: str, description: str, image_attributes, num_tries=3) -> str:
    for _ in range(num_tries):
        try:
            return image_creator.generate_and_upload(symbol, name, description, image_attributes)
        except Exception as e:
            print(f"Error creating image: {e}")
            time.sleep(5)
    return ""


def get_creation_fee() -> int:
    """Query the token factory contract for the current creation fee amount.

    Returns:
        int: The creation fee amount in wei
    """
    contract = ch.web3.eth.contract(
        address=ch.web3.to_checksum_address(ch.TOKEN_FACTORY_ADDRESS),
        abi=abis.meme_manager_abi,
    )
    return contract.functions.creationDeveloperFeeAmount().call()


def create_memecoin(name: str, symbol: str, description: str, image_attributes: str, account: LocalAccount) -> bool:
    # Step 0: Get balance
    balances = query_balances.get_balances(account.address)
    for token in balances:
        if token['symbol'].lower() == symbol.lower():
            return False
        if token['name'].lower() == name.lower():
            return False
    # Step 1: Create the image
    image_ipfs = try_creating_image(symbol, name, description, image_attributes)
    if image_ipfs == "":
        print("Failed to create image. Cannot create memecoin")
        return False

    # Step 2: Grab creation fee
    creation_fee = get_creation_fee()

    # Step 3: Prepare createToken call
    factory_contract = ch.web3.eth.contract(
        address=ch.web3.to_checksum_address(ch.TOKEN_FACTORY_ADDRESS),
        abi=abis.meme_manager_abi,
    )
    direct_tx = factory_contract.functions.createAndBuyToken(
        name,
        symbol,
        description,
        image_ipfs,
        f"https://twitter.com/{agent_interests.TWITTER_HANDLE}",
        agent_interests.TG_INVITE_LINK,
        f"https://echos.fun/{agent_interests.BOT_NAME.lower()}",
        ch.INITIAL_BUY,
    ).build_transaction(
        {  # type: ignore
            "from": account.address,
            "nonce": ch.web3.eth.get_transaction_count(account.address),
            "gas": 6_000_000,
            "gasPrice": ch.GAS_PRICE,
            "chainId": ch.CHAIN_ID,
            "value": creation_fee + ch.INITIAL_BUY,
        }
    )

    # Step 4: Sign and send transaction
    receipt = ch.sign_and_send_tx(account, direct_tx)

    if receipt.get('status') == 1:
        # Grab token address from the token creation event (log index 2)
        token_address = '0x' + receipt['logs'][2]['topics'][1].hex()[-40:]
        token_address = ch.web3.to_checksum_address(token_address)
        print(f"Token creation succeeded. New token address: {token_address}")
        return True
    else:
        print("Token creation failed")
        print(f"Full receipt: {receipt}")
        return False
