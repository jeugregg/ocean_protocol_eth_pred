import asyncio
import json

from main_bot import run_close_trade_request, get_open_logical_order
from lighter_exec import build_client, load_states


async def close_trade():
    # ===== PARAMS =====
    symbol = "ETH"
    # ==================

    trading_state, bot_state = load_states()
    order = get_open_logical_order(trading_state, bot_state)

    if not order:
        print("No open trade to close.")
        return

    client, api_client, order_api, auth_token = build_client()

    side = order["side"]
    size = order["filled_base_amount"]

    trade_request = {
        "symbol": symbol,
        "side": side,
        "size": size,
        "worst_slippage": 0.02,
    }

    print("==== CLOSE TRADE REQUEST ====")
    print(json.dumps(trade_request, indent=2))

    try:
        result = await run_close_trade_request(
            trade_request, client, api_client, order_api, auth_token
        )
        print("\n==== CLOSE TRADE RESULT ====")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

        if not result.get("ok"):
            print("\nClose refused.")
            return

    except Exception as e:
        print(f"\nExecution error: {e}")
        return

    finally:
        await api_client.close()
        await client.close()


if __name__ == "__main__":
    asyncio.run(close_trade())
