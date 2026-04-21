import asyncio
import json

from main_bot import run_trade_request
from lighter_exec import build_client, get_market_id


async def main():
    # ===== PARAMS =====
    symbol = "ETH"
    mode_long = True
    total_base_amount = int(0.02 * 10000)  # 0.02 ETH si BASE_SCALE = 10000
    tp_ratio_1 = 0.25 / 100  # +0.25%
    tp_ratio_2 = 0.45 / 100  # +0.45%
    R = 2  # SL = TP2 / R
    slippage = 0.01  # 1%
    use_same_entry_price_for_both = True
    timeout_minutes = 60
    rep_tp1 = 0.7  # 50% at TP1, 50% at TP2 (0 to 1)
    # ==================

    size = total_base_amount / 10000.0
    side = "LONG" if mode_long else "SHORT"

    client, api_client, order_api, auth_token = build_client()

    try:
        market_id = await get_market_id(order_api, symbol)

        res_ob = await order_api.order_book_details(market_id=market_id)
        last_trade_price = float(res_ob.order_book_details[0].last_trade_price)

        entry_price = last_trade_price

        if mode_long:
            tp1 = entry_price * (1 + tp_ratio_1)
            tp2 = entry_price * (1 + tp_ratio_2)
            sl = entry_price * (1 - tp_ratio_2 / R)
        else:
            tp1 = entry_price * (1 - tp_ratio_1)
            tp2 = entry_price * (1 - tp_ratio_2)
            sl = entry_price * (1 + tp_ratio_2 / R)

        trade_request = {
            "symbol": f"{symbol}USDT",
            "side": side,
            "entry_price": round(entry_price, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp2, 2),
            "sl": round(sl, 2),
            "size": size,
            "timeout_minutes": timeout_minutes,
            "order_type": "limit",
            "entry_slippage": 0.0,
            "exit_slippage": slippage,
            "rep_tp1": rep_tp1,
        }

        print("==== TRADE REQUEST ====")
        for k, v in trade_request.items():
            print(f"{k}: {v}")
        print("Config helper use_same_entry_price_for_both:", use_same_entry_price_for_both)

        result = await run_trade_request(trade_request, client, api_client, order_api, auth_token)
        print("\n==== TRADE RESULT ====")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

        if not result.get("ok"):
            print("\nTrade refused.")
            return

        if result.get("position_open"):
            print("\nPosition opened successfully.")
        else:
            print("\nWarning: Position may not be confirmed.")

    except Exception as e:
        print(f"\nExecution error: {e}")
        return

    finally:
        await api_client.close()
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
