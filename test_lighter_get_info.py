import os
import time
import asyncio
import datetime
import lighter
import logging


logging.basicConfig(level=logging.INFO)
# import env var
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

BASE_URL = os.getenv("LIGHTER_BASE_URL")
L1_ADDRESS = os.getenv("LIGHTER_PUBLIC_ADDRESS")
ACCOUNT_INDEX = int(os.getenv("LIGHTER_ACCOUNT_INDEX"))
PRIVATE_KEY = os.getenv("LIGHTER_API_KEY")
API_KEY_INDEX = int(os.getenv("LIGHTER_API_KEY_INDEX"))

async def print_api(method, *args, **kwargs):
    logging.info(f"{method.__name__}: {await method(*args, **kwargs)}")


async def account_apis(client: lighter.ApiClient):
    logging.info("ACCOUNT APIS")
    account_instance = lighter.AccountApi(client)
    await print_api(account_instance.account, by="l1_address", value=L1_ADDRESS)
    await print_api(account_instance.account, by="index", value=str(ACCOUNT_INDEX))
    await print_api(account_instance.accounts_by_l1_address, l1_address=L1_ADDRESS)
    await print_api(account_instance.apikeys, account_index=ACCOUNT_INDEX, api_key_index=API_KEY_INDEX)
    #await print_api(account_instance.public_pools, filter="all", limit=1, index=0)


async def block_apis(client: lighter.ApiClient):
    logging.info("BLOCK APIS")
    block_instance = lighter.BlockApi(client)
    await print_api(block_instance.block, by="height", value="150013259")
    await print_api(block_instance.blocks, index=0, limit=2, sort="asc")
    await print_api(block_instance.current_height)


async def candlestick_apis(client: lighter.ApiClient):
    logging.info("CANDLESTICK APIS")
    candlestick_instance = lighter.CandlestickApi(client)
    await print_api(
        candlestick_instance.candlesticks,
        market_id=0,
        resolution="1h",
        start_timestamp=int(datetime.datetime.now().timestamp() - 60 * 60 * 24),
        end_timestamp=int(datetime.datetime.now().timestamp()),
        count_back=2,
    )
    await print_api(
        candlestick_instance.fundings,
        market_id=0,
        resolution="1h",
        start_timestamp=int(datetime.datetime.now().timestamp() - 60 * 60 * 24),
        end_timestamp=int(datetime.datetime.now().timestamp()),
        count_back=2,
    )


async def order_apis(client: lighter.ApiClient):
    logging.info("ORDER APIS")
    order_instance = lighter.OrderApi(client)
    await print_api(order_instance.exchange_stats)
    await print_api(order_instance.order_book_details, market_id=0)
    await print_api(order_instance.order_books)
    await print_api(order_instance.recent_trades, market_id=0, limit=2)


async def transaction_apis(client: lighter.ApiClient):
    logging.info("TRANSACTION APIS")
    transaction_instance = lighter.TransactionApi(client)
    await print_api(transaction_instance.block_txs, by="block_height", value="1")
    await print_api(
        transaction_instance.next_nonce,
        account_index=int(ACCOUNT_INDEX),
        api_key_index=0,
    )
    # use with a valid sequence index
    # await print_api(transaction_instance.tx, by="sequence_index", value="5")
    await print_api(transaction_instance.txs, index=0, limit=2)
    
async def funding_apis(client: lighter.ApiClient):
    logging.info("FUNDING APIS")
    account_instance = lighter.FundingApi(client)
    await print_api(account_instance.funding_rates)

async def main():
    api_client = lighter.ApiClient(configuration=lighter.Configuration(host=BASE_URL))
    client = lighter.SignerClient(  
        url=BASE_URL,  
        api_private_keys={API_KEY_INDEX:PRIVATE_KEY},  
        account_index=ACCOUNT_INDEX,
    )

    await account_apis(api_client)
    await block_apis(api_client)
    await candlestick_apis(api_client)
    await order_apis(api_client)
    await transaction_apis(api_client)
    await funding_apis(api_client)
    await api_client.close()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())