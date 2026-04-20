import os
import time
import json
import asyncio
import logging
import requests
import lighter

from dotenv import load_dotenv, find_dotenv
from lighter.signer_client import CreateOrderTxReq

logging.basicConfig(level=logging.INFO)
load_dotenv(find_dotenv())

BASE_URL = os.getenv("LIGHTER_BASE_URL")
ACCOUNT_INDEX = int(os.getenv("LIGHTER_ACCOUNT_INDEX"))
PRIVATE_KEY = os.getenv("LIGHTER_API_KEY")
API_KEY_INDEX = int(os.getenv("LIGHTER_API_KEY_INDEX"))

MARKET_INDEX = 0
MARKETS_URL = "https://explorer.elliot.ai/api/markets"

BASE_CID = int(time.time()) % (2**48 - 100)

def build_cids(base):
    return {
        "entry_1": base,
        "tp_1": base + 1,
        "sl_1": base + 2,
        "entry_2": base + 3,
        "tp_2": base + 4,
        "sl_2": base + 5,
    }

def get_market_id(symbol="ETH"):
    response = requests.get(MARKETS_URL, headers={"accept": "application/json"}, timeout=10)
    response.raise_for_status()
    markets = response.json()
    return [x for x in markets if x["symbol"] == symbol][0]["market_index"]

async def main():
    # ========= PARAMS =========
    symbol = "ETH"
    mode_long = True              # True = long, False = short
    total_base_amount = int(0.02 * 10000)   # 0.02 ETH si 10000 = 1 ETH
    tp_ratio_1 = 0.25 / 100       # +0.25%
    tp_ratio_2 = 0.45 / 100       # +0.45%
    R = 2                         # SL = TP2 / R, par exemple
    slippage = 0.01               # 1%
    use_same_entry_price_for_both = True

    # vraie limite qui reste dans le book
    entry_offset = 0.0            # 0.0 = au dernier trade, ajuste si besoin
    # ex: pour long agressif mais limite: +0.02/100 ; pour short: -0.02/100

    cids = build_cids(BASE_CID)

    client = lighter.SignerClient(
        url=BASE_URL,
        api_private_keys={API_KEY_INDEX: PRIVATE_KEY},
        account_index=ACCOUNT_INDEX,
    )
    api_client = client.api_client
    client.check_client()

    try:
        market_id = get_market_id(symbol)
        print("market_id:", market_id)

        # sécurité simple : ne pas ouvrir si position déjà ouverte
        account_api = lighter.AccountApi(api_client)
        account_info = await account_api.account(by="index", value=str(ACCOUNT_INDEX))

        position_curr = 0.0
        if account_info.accounts and account_info.accounts[0].positions:
            position_curr = float(account_info.accounts[0].positions[0].position)

        print("position_curr:", position_curr)
        if position_curr != 0:
            raise Exception("Position déjà ouverte, script stoppé.")

        res_ob = await client.order_api.order_book_details(market_id=market_id)
        last_trade_price = int(res_ob.order_book_details[0].last_trade_price * 100)
        print("last_trade_price:", last_trade_price)

        # ========= ENTRY PRICE =========
        if mode_long:
            entry_price = int(last_trade_price * (1 + entry_offset))
        else:
            entry_price = int(last_trade_price * (1 - entry_offset))

        # ========= TP / SL =========
        if mode_long:
            tp1_trigger = int(entry_price * (1 + tp_ratio_1))
            tp1_limit   = int(tp1_trigger * (1 - slippage))

            tp2_trigger = int(entry_price * (1 + tp_ratio_2))
            tp2_limit   = int(tp2_trigger * (1 - slippage))

            sl_trigger  = int(entry_price * (1 - tp_ratio_2 / R))
            sl_limit    = int(sl_trigger * (1 - slippage))

            entry_is_ask = 0
            exit_is_ask = 1

        else:
            tp1_trigger = int(entry_price * (1 - tp_ratio_1))
            tp1_limit   = int(tp1_trigger * (1 + slippage))

            tp2_trigger = int(entry_price * (1 - tp_ratio_2))
            tp2_limit   = int(tp2_trigger * (1 + slippage))

            sl_trigger  = int(entry_price * (1 + tp_ratio_2 / R))
            sl_limit    = int(sl_trigger * (1 + slippage))

            entry_is_ask = 1
            exit_is_ask = 0

        qty_1 = total_base_amount // 2
        qty_2 = total_base_amount - qty_1

        print("entry_price:", entry_price)
        print("qty_1:", qty_1, "qty_2:", qty_2)
        print("tp1_trigger:", tp1_trigger, "tp1_limit:", tp1_limit)
        print("tp2_trigger:", tp2_trigger, "tp2_limit:", tp2_limit)
        print("sl_trigger:", sl_trigger, "sl_limit:", sl_limit)

        grouping_type = client.GROUPING_TYPE_ONE_TRIGGERS_A_ONE_CANCELS_THE_OTHER

        # ========= GROUP 1 =========
        entry_1 = CreateOrderTxReq(
            MarketIndex=market_id,
            ClientOrderIndex=cids["entry_1"],
            BaseAmount=qty_1,
            Price=entry_price,
            IsAsk=entry_is_ask,
            Type=client.ORDER_TYPE_LIMIT,
            TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            ReduceOnly=0,
            TriggerPrice=0,
            OrderExpiry=-1,
        )

        tp_1 = CreateOrderTxReq(
            MarketIndex=market_id,
            ClientOrderIndex=cids["tp_1"],
            BaseAmount=0,
            Price=tp1_limit,
            IsAsk=exit_is_ask,
            Type=client.ORDER_TYPE_TAKE_PROFIT_LIMIT,
            TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            ReduceOnly=1,
            TriggerPrice=tp1_trigger,
            OrderExpiry=-1,
        )

        sl_1 = CreateOrderTxReq(
            MarketIndex=market_id,
            ClientOrderIndex=cids["sl_1"],
            BaseAmount=0,
            Price=sl_limit,
            IsAsk=exit_is_ask,
            Type=client.ORDER_TYPE_STOP_LOSS_LIMIT,
            TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            ReduceOnly=1,
            TriggerPrice=sl_trigger,
            OrderExpiry=-1,
        )

        # ========= GROUP 2 =========
        entry_price_2 = entry_price if use_same_entry_price_for_both else entry_price

        entry_2 = CreateOrderTxReq(
            MarketIndex=market_id,
            ClientOrderIndex=cids["entry_2"],
            BaseAmount=qty_2,
            Price=entry_price_2,
            IsAsk=entry_is_ask,
            Type=client.ORDER_TYPE_LIMIT,
            TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            ReduceOnly=0,
            TriggerPrice=0,
            OrderExpiry=-1,
        )

        tp_2 = CreateOrderTxReq(
            MarketIndex=market_id,
            ClientOrderIndex=cids["tp_2"],
            BaseAmount=0,
            Price=tp2_limit,
            IsAsk=exit_is_ask,
            Type=client.ORDER_TYPE_TAKE_PROFIT_LIMIT,
            TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            ReduceOnly=1,
            TriggerPrice=tp2_trigger,
            OrderExpiry=-1,
        )

        sl_2 = CreateOrderTxReq(
            MarketIndex=market_id,
            ClientOrderIndex=cids["sl_2"],
            BaseAmount=0,
            Price=sl_limit,
            IsAsk=exit_is_ask,
            Type=client.ORDER_TYPE_STOP_LOSS_LIMIT,
            TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            ReduceOnly=1,
            TriggerPrice=sl_trigger,
            OrderExpiry=-1,
        )

        print("Sending grouped order 1...")
        tx1, tx_hash1, err1 = await client.create_grouped_orders(
            grouping_type=grouping_type,
            orders=[entry_1, tp_1, sl_1],
        )
        print("tx1:", tx1)
        print("tx_hash1:", tx_hash1)
        print("err1:", err1)

        if err1 is not None:
            raise Exception(f"Groupe 1 error: {err1}")

        print("Sending grouped order 2...")
        tx2, tx_hash2, err2 = await client.create_grouped_orders(
            grouping_type=grouping_type,
            orders=[entry_2, tp_2, sl_2],
        )
        print("tx2:", tx2)
        print("tx_hash2:", tx_hash2)
        print("err2:", err2)

        if err2 is not None:
            raise Exception(f"Groupe 2 error: {err2}")

        print("OK: 2 groupes envoyés.")

    finally:
        await api_client.close()
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())