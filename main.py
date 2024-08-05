import os
import json
import asyncio
import requests
from dotenv import load_dotenv
from starknet_py.net.client_models import Call
from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.models.chains import StarknetChainId
from starknet_py.net.signer.stark_curve_signer import KeyPair
from starknet_py.hash.selector import get_selector_from_name


load_dotenv()
address = os.getenv("ADDRESS")
private_key = os.getenv("PRIVATE_KEY")
provider_url = os.getenv("PROVIDER_URL")
sell_token_address = os.getenv("SELL_TOKEN_ADDRESS")
buy_token_address = os.getenv("BUY_TOKEN_ADDRESS")
sell_amount = os.getenv("SELL_AMOUNT")
slippage = os.getenv("SLIPPAGE")
accept_language = os.getenv("ACCEPT_LANGUAGE")
sec_ch_ua = os.getenv("SEC_CH_UA")
sec_ch_ua_platform = os.getenv("SEC_CH_UA_PLATFORM")
user_agent = os.getenv("USER_AGENT")


def quotePrice():
    url_quote = "https://starknet.api.avnu.fi/internal/swap/quotes-with-prices"
    params_quote = {
        "sellTokenAddress": sell_token_address,
        "buyTokenAddress": buy_token_address,
        "sellAmount": sell_amount,
        "takerAddress": address,
        "size": 3,
        "excludeSources": [
            "10kSwap", "Ekubo", "Haiko", "HaikoStrategy", "JediSwap", "JediSwapCL",
            "MySwap", "MySwapCL", "SithSwap", "StarkDefi", "StarkWare"
        ],
        "integratorName": "AVNU Portal"
    }

    headers_quote = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": accept_language,
        "origin": "https://app.avnu.fi",
        "referer": "https://app.avnu.fi/",
        "sec-ch-ua": sec_ch_ua,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": sec_ch_ua_platform,
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "sec-gpc": "1",
        "user-agent": user_agent
    }

    response_quote = requests.get(url_quote, headers=headers_quote, params=params_quote)
    data_quote = response_quote.json()
    quote_id = data_quote["quotes"][0]["quoteId"]
    print(f"Quote status: {response_quote.status_code}")
    return quote_id


def buildTXN(quote_id):
    url_build = "https://starknet.api.avnu.fi/swap/v2/build"
    headers_build = {
        "accept": "application/json",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": accept_language,
        "ask-signature": "true",
        "content-length": "172",
        "content-type": "application/json",
        "origin": "https://app.avnu.fi",
        "referer": "https://app.avnu.fi/",
        "sec-ch-ua": sec_ch_ua,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": sec_ch_ua_platform,
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "sec-gpc": "1",
        "user-agent": user_agent
    }

    payload_build = {
        "quoteId": quote_id,
        "takerAddress": address,
        "slippage": float(slippage),
        "includeApprove": True
    }

    response_build = requests.post(url_build, headers=headers_build, data=json.dumps(payload_build))
    data_build = response_build.json()
    print(f"Build status: {response_build.status_code}")
    return data_build


async def executeTXN(data_build):
    client = FullNodeClient(node_url=provider_url)
    account = Account(
        client=client,
        address=address,
        key_pair=KeyPair.from_private_key(key=private_key),
        chain=StarknetChainId.MAINNET,
    )
    print(f"Nonce: {await account.get_nonce()}")

    calls = data_build["calls"]

    decimal_approve_call = [int(hex_str, 16) for hex_str in calls[0]["calldata"]]
    approve_call = Call(
        to_addr=int(calls[0]["contractAddress"], 16),
        selector=get_selector_from_name(calls[0]["entrypoint"]),
        calldata=decimal_approve_call
    )

    decimal_multi_route_swap_call = [int(hex_str, 16) for hex_str in calls[1]["calldata"]]
    multi_route_swap_call = Call(
        to_addr=int(calls[1]["contractAddress"], 16),
        selector=get_selector_from_name(calls[1]["entrypoint"]),
        calldata=decimal_multi_route_swap_call
    )

    resp = await account.execute_v3([approve_call, multi_route_swap_call], auto_estimate=True)
    print(f"TXN status: {resp}")
    await account.client.wait_for_tx(resp.transaction_hash)
    print(f"TXN {resp.transaction_hash} finished.");


async def main():
    success = 0
    failed = 0

    while 1:
        print("----------------------------------------TXN Start----------------------------------------")
        try:
            quote_id = quotePrice()
            data_build = buildTXN(quote_id)
            await executeTXN(data_build)
            success += 1
            print(f"--------------------✅TXN Successful, success: {success} failed: {failed}--------------------\n")
        except Exception as e:
            print(e)
            failed += 1
            print(f"--------------------❌TXN Failed, success: {success} failed: {failed}--------------------\n")
            await asyncio.sleep(10)
            # break


asyncio.run(main())