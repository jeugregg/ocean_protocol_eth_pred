import asyncio

from state_manager import (
    ensure_state_files,
    load_states,
    get_last_trade_signal,
    get_open_logical_order,
    should_force_close,
)
from lighter_exec import (
    build_client,
    place_trade_on_lighter,
    sync_lighter_state,
    close_position_market,
)

DEFAULT_TRADE_SIZE = 0.02
DEFAULT_TIMEOUT_MINUTES = 60


async def run_trade_request(trade_request: dict):
    ensure_state_files()

    client, api_client = build_client()

    try:
        sync_before = await sync_lighter_state(api_client)
        print("SYNC BEFORE:", sync_before)

        trading_state, bot_state = load_states()
        open_order = get_open_logical_order(trading_state, bot_state)

        if open_order:
            return {
                "ok": False,
                "reason": "order_already_live",
                "message": f"Ordre déjà vivant: {open_order['id']} ({open_order['status']})",
                "open_order": {
                    "id": open_order.get("id"),
                    "status": open_order.get("status"),
                    "symbol": open_order.get("symbol"),
                    "side": open_order.get("side"),
                    "price": open_order.get("price"),
                    "size": open_order.get("size"),
                    "tp1": open_order.get("tp1"),
                    "tp2": open_order.get("tp2"),
                    "sl": open_order.get("sl"),
                },
                "sync_before": sync_before,
            }

        symbol = trade_request["symbol"]
        side = trade_request["side"].upper()
        entry_price = float(trade_request["entry_price"])
        tp1 = float(trade_request["tp1"])
        tp2 = float(trade_request["tp2"])
        sl = float(trade_request["sl"])
        size = float(trade_request.get("size", DEFAULT_TRADE_SIZE))
        timeout_minutes = int(trade_request.get("timeout_minutes", DEFAULT_TIMEOUT_MINUTES))
        order_type = trade_request.get("order_type", "limit")
        entry_slippage = float(trade_request.get("entry_slippage", 0.0))
        exit_slippage = float(trade_request.get("exit_slippage", 0.01))

        result = await place_trade_on_lighter(
            client=client,
            api_client=api_client,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            tp1=tp1,
            tp2=tp2,
            sl=sl,
            size=size,
            timeout_minutes=timeout_minutes,
            order_type=order_type,
            entry_slippage=entry_slippage,
            exit_slippage=exit_slippage,
        )
        print("PLACE RESULT:", result)

        sync_after = await sync_lighter_state(api_client)
        print("SYNC AFTER:", sync_after)

        return {
            "ok": True,
            "reason": "trade_sent",
            "result": result,
            "sync_after": sync_after,
        }

    except Exception as e:
        return {
            "ok": False,
            "reason": "execution_error",
            "message": str(e),
        }

    finally:
        await api_client.close()
        await client.close()


async def run_from_bot_state():
    ensure_state_files()
    trading_state, bot_state = load_states()

    client, api_client = build_client()

    try:
        sync_before = await sync_lighter_state(api_client)
        print("SYNC BEFORE:", sync_before)

        trading_state, bot_state = load_states()
        open_order = get_open_logical_order(trading_state, bot_state)

        if open_order:
            print("Ordre déjà vivant:", open_order["id"], open_order["status"])

            if should_force_close(open_order):
                current_pos = bot_state.get("current_position")
                if current_pos:
                    print("Timeout atteint -> fermeture marché")
                    await close_position_market(
                        client=client,
                        api_client=api_client,
                        symbol=open_order["symbol"],
                        side=open_order["side"],
                        size=current_pos["size"],
                        worst_slippage=0.02,
                    )
                    sync_after_close = await sync_lighter_state(api_client)
                    print("SYNC AFTER CLOSE:", sync_after_close)
                    return {
                        "ok": True,
                        "mode": "state_only",
                        "action": "force_close_sent",
                        "sync_after_close": sync_after_close,
                    }

            return {
                "ok": True,
                "mode": "state_only",
                "action": "existing_order_detected",
                "open_order": {
                    "id": open_order.get("id"),
                    "status": open_order.get("status"),
                    "symbol": open_order.get("symbol"),
                    "side": open_order.get("side"),
                    "price": open_order.get("price"),
                    "size": open_order.get("size"),
                    "tp1": open_order.get("tp1"),
                    "tp2": open_order.get("tp2"),
                    "sl": open_order.get("sl"),
                },
            }

        signal = get_last_trade_signal(bot_state)
        if not signal:
            return {
                "ok": False,
                "reason": "no_signal",
                "message": "Aucun signal exploitable dans bot_state.json",
            }

        result = await place_trade_on_lighter(
            client=client,
            api_client=api_client,
            symbol=signal["symbol"],
            side=signal["side"],
            entry_price=signal["entry_price"],
            tp1=signal["tp1"],
            tp2=signal["tp2"],
            sl=signal["sl"],
            size=DEFAULT_TRADE_SIZE,
            timeout_minutes=DEFAULT_TIMEOUT_MINUTES,
            order_type="limit",
            entry_slippage=0.0,
            exit_slippage=0.01,
        )
        print("PLACE RESULT:", result)

        sync_after = await sync_lighter_state(api_client)
        print("SYNC AFTER:", sync_after)

        return {
            "ok": True,
            "mode": "bot_state",
            "reason": "trade_sent",
            "result": result,
            "sync_after": sync_after,
        }

    except Exception as e:
        return {
            "ok": False,
            "mode": "bot_state",
            "reason": "execution_error",
            "message": str(e),
        }

    finally:
        await api_client.close()
        await client.close()


async def run_sync_only():
    ensure_state_files()

    client, api_client = build_client()

    try:
        sync = await sync_lighter_state(api_client)

        trading_state, bot_state = load_states()
        open_order = get_open_logical_order(trading_state, bot_state)

        return {
            "ok": True,
            "reason": "sync_only",
            "sync": sync,
            "open_order": {
                "id": open_order.get("id"),
                "status": open_order.get("status"),
                "symbol": open_order.get("symbol"),
                "side": open_order.get("side"),
                "price": open_order.get("price"),
                "size": open_order.get("size"),
                "tp1": open_order.get("tp1"),
                "tp2": open_order.get("tp2"),
                "sl": open_order.get("sl"),
            } if open_order else None,
            "current_position": bot_state.get("current_position"),
            "pending_order": bot_state.get("pending_order"),
        }

    except Exception as e:
        return {
            "ok": False,
            "reason": "sync_error",
            "message": str(e),
        }

    finally:
        await api_client.close()
        await client.close()

if __name__ == "__main__":
    result = asyncio.run(run_from_bot_state())
    print(result)