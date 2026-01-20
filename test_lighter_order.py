# TEST ORDER LIGHTER

    # Example LONG position with SL/TP at all costs
    # Buy some ETH at $2500
    # The size of the SL/TP orders will be equal to the size of the executed order
    # set SL trigger price at 2000 and worst price at 1980 (-1%)
    # set TP trigger price at 3000 and worst price at 2970 (-1%)

    # Example for a SHORT position with SL/TP
    # Sell some ETH at $2500
    # The size of the SL/TP orders will be equal to the size of the executed order
    # set SL trigger price at 5000 and limit price at 5050
    # set TP trigger price at 1500 and limit price at 1550
    # Note: set the limit price to be higher than the SL/TP trigger price to ensure the order will be filled
    # If the mark price of ETH reaches 1500, there might be no one willing to sell you ETH at 1500, 
    # so trying to buy at 1550 would increase the fill rate

# DONE : SL not working yet
# DONE : get current market-price just before send tx (with last trade price only , not real index proce of orderbook)
# DONE : check state of the position and orders
# DONE : try a delay one hour to close the trade even if still open
# TODO : fix issue with ioc SL/TP order group with Expirity

import os
import time
from datetime import datetime
import asyncio
import lighter
import logging
import requests
import json
from lighter.signer_client import CreateOrderTxReq

logging.basicConfig(level=logging.INFO)
# import env var
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

BASE_URL = os.getenv("LIGHTER_BASE_URL")
L1_ADDRESS = os.getenv("LIGHTER_PUBLIC_ADDRESS")
ACCOUNT_INDEX = int(os.getenv("LIGHTER_ACCOUNT_INDEX"))
PRIVATE_KEY = os.getenv("LIGHTER_API_KEY")
API_KEY_INDEX = int(os.getenv("LIGHTER_API_KEY_INDEX"))
MARKET_INDEX = 0 # ETH futures ?


url = "https://explorer.elliot.ai/api/markets"

headers = {"accept": "application/json"}

response = requests.get(url, headers=headers)

MARKET_LIST = json.loads(response.text)

async def main():
    mode_open = True # by default we want to open long position

    client = lighter.SignerClient(  
        url=BASE_URL,  
        api_private_keys={API_KEY_INDEX:PRIVATE_KEY},  
        account_index=ACCOUNT_INDEX,
    )
    #api_client = lighter.ApiClient(configuration=lighter.Configuration(host=BASE_URL))
    api_client = client.api_client
    # get state of order if exists
    # check if there is an open position
    account_api = lighter.AccountApi(api_client)

    account_info = await account_api.account(by="index", value=str(ACCOUNT_INDEX))

    print("account_info: ", account_info)
    position_curr = float(account_info.accounts[0].positions[0].position)
    print("position curr: ", position_curr)

    state_open_pos = position_curr != 0
    print("state_open_pos: ", state_open_pos)

    mode_close = False
    # do TX ?
    if state_open_pos:
        timestamp_open = account_info.accounts[0].additional_properties["transaction_time"]/1000/1000
        print("time_open: ", datetime.fromtimestamp(timestamp_open).strftime('%Y-%m-%d %H:%M:%S'))
        # check if time since open > 1h
        timestamp_now = time.time()
        time_since_open = timestamp_now - timestamp_open
        mode_close = time_since_open >= 60*60   # 1h
        print("mode_close: ", mode_close)

        if mode_close:
            # close position
            mode_tx = True
            mode_open = False
        else:
            mode_tx = False
                    
    else:
        mode_tx = True

    print("mode_tx: ", mode_tx)

    # TEST
    #mode_tx = True

    #print(MARKET_LIST)
    # get ETH futures
    market_id = [x for x in MARKET_LIST if x["symbol"]=="ETH" ][0]['market_index']
    print("market_id: ", market_id)

    # get market price
    res_orderbook_details = await client.order_api.order_book_details(market_id=MARKET_INDEX)
    price_market = int(res_orderbook_details.order_book_details[0].last_trade_price * 100)
    print("market_price: ", price_market)


    if mode_open:
        #price_market = 3315*100 # need to get it from the API ?
        R = 2
        tp_ratio = 0.45/100 # 0.45/100
        price_maxi = int(price_market * 1.01) # price maxi to exceute market order

        price_sl_trigger = int(price_market*(1-tp_ratio/R))
        price_tp_trigger = int(price_market*(1+tp_ratio))

        price_sl_worst = int(price_market*(1-tp_ratio/R)*0.99)
        price_tp_worst = int(price_market*(1+tp_ratio/R)*0.99)

        # print
        print("tp_ratio: ", tp_ratio)
        print("price_maxi: ", price_maxi)
        print("price_market: ", price_market)
        print("price_sl_trigger: ", price_sl_trigger)
        print("price_tp_trigger: ", price_tp_trigger)
        print("price_sl_worst: ", price_sl_worst)
        print("price_tp_worst: ", price_tp_worst)

        # Create a One-Cancels-the-Other grouped order
        ioc_order = CreateOrderTxReq(
            MarketIndex=market_id,
            ClientOrderIndex=0,
            BaseAmount=int(0.02*10000),  # 10000 = 1 ETH
            Price=price_maxi,  # market price + 1%
            IsAsk=0, # buy
            Type=client.ORDER_TYPE_MARKET,
            TimeInForce=client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
            ReduceOnly=0,
            TriggerPrice=0,
            OrderExpiry=0,
        )

        # Create a One-Cancels-the-Other grouped order with a take-profit and a stop-loss order
        take_profit_order = CreateOrderTxReq(
            MarketIndex=market_id,
            ClientOrderIndex=0,
            BaseAmount=0,
            Price=price_tp_worst,
            IsAsk=1, # sell
            Type=client.ORDER_TYPE_TAKE_PROFIT,
            #TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            ReduceOnly=1,
            TriggerPrice=price_tp_trigger,
            OrderExpiry=-1,
        )

        stop_loss_order = CreateOrderTxReq(
            MarketIndex=market_id,
            ClientOrderIndex=0,
            BaseAmount=0,
            Price=price_sl_worst, # 
            IsAsk=1, # sell
            Type=client.ORDER_TYPE_STOP_LOSS,
            #TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            ReduceOnly=1,
            TriggerPrice=price_sl_trigger,
            OrderExpiry=-1,
        )

        if mode_tx:

            tx, tx_hash, err = await client.create_grouped_orders(
                grouping_type=client.GROUPING_TYPE_ONE_TRIGGERS_A_ONE_CANCELS_THE_OTHER,
                orders=[ioc_order, take_profit_order, stop_loss_order],
            )
            print("Create Grouped Order")
            print("tx: ", tx)
            print("tx_hash: ", tx_hash)
            print("err: ", err)

    # tx, tx_hash, err = await client.create_market_order(
    #     market_index=market_id,
    #     client_order_index=0,
    #     base_amount=int(0.02*10000),  # 0.1 ETH
    #     avg_execution_price=4000_00,  # $4000 -- worst acceptable price for the order
    #     is_ask=0,
    # )
    # print(f"Create Order {tx=} {tx_hash=} {err=}")
    # if err is not None:
    #     raise Exception(err)
    if mode_close:
        # close position
        price_worst = int(price_market * 0.90)  # important worst price -10% market price
        
        if mode_tx:
            print("close position...")
            # Create a Sell order the same position with worst price (lower price)
            tx, tx_hash, err = await client.create_market_order(
                market_index=market_id,
                client_order_index=0,
                base_amount=int(0.02*10000),  # 10000 = 1 ETH
                avg_execution_price=price_worst, # -- worst acceptable price for the order
                is_ask=1, # sell
            )
            print(f"Create Sell Market Order {tx=} {tx_hash=} {err=}")
       

    await api_client.close()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())