import asyncio
import json

from main_bot import run_close_trade_request
from lighter_exec import build_client


async def close_trade():
    """Close any open position automatically."""
    # Optional: override slippage if needed
    trade_request = {
        "worst_slippage": 0.02,  # Override if needed
    }

    print("==== AUTO CLOSE TRADE ====")
    print("Detecting and closing any open position...")

    client, api_client, order_api, auth_token = build_client()

    try:
        result = await run_close_trade_request(
            trade_request, client, api_client, order_api, auth_token
        )
        print("\n==== CLOSE TRADE RESULT ====")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

        if not result.get("ok"):
            print("\nClose operation failed or no position to close.")
            return

        if result.get("position_closed"):
            print("\nPosition closed successfully.")
        else:
            print("\nWARNING: Position may still be open.")

    except Exception as e:
        print(f"\nExecution error: {e}")
        return

    finally:
        await api_client.close()
        await client.close()


if __name__ == "__main__":
    asyncio.run(close_trade())
