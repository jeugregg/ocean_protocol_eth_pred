import asyncio
import json

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


async def run_trade_request(trade_request: dict, client, api_client, order_api, auth_token):
    ensure_state_files()

    try:
        sync_before = await sync_lighter_state(order_api, auth_token)
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
            order_api=order_api,
            auth_token=auth_token,
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

        sync_after = await sync_lighter_state(order_api, auth_token)
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


async def run_close_trade_request(trade_request: dict, client, api_client, order_api, auth_token):
    """Close an open position with pre/post sync verification."""
    ensure_state_files()

    try:
        # Pre-close sync
        sync_before = await sync_lighter_state(order_api, auth_token)
        print("SYNC BEFORE CLOSE:", sync_before)

        current_position = sync_before.get("current_position")
        if not current_position:
            return {
                "ok": False,
                "reason": "no_position",
                "message": "No open position detected.",
                "sync_before": sync_before,
            }

        symbol = trade_request.get("symbol", "ETH")  # e.g., "ETH" or "ETHUSDT"
        side = trade_request.get("side")  # "LONG" or "SHORT"
        size_base = float(trade_request.get("size", current_position.get("size", 0.02)))
        worst_slippage = float(trade_request.get("worst_slippage", 0.02))

        # Send close market order
        result = await close_position_market(
            client=client,
            api_client=api_client,
            symbol=symbol,
            side=side,
            size=size_base,
            worst_slippage=worst_slippage,
        )
        print("CLOSE POSITION SENT:", result)

        # Post-close sync/polling
        print("\n==== POST-CLOSE SYNC LOOP ====")
        for i in range(1, 6):
            await asyncio.sleep(2.0)
            sync_after = await sync_lighter_state(order_api, auth_token)
            print(f"[SYNC {i}] {json.dumps(sync_after, indent=2, ensure_ascii=False, default=str)}")

            current_position = sync_after.get("current_position")
            if not current_position:
                print(f"[SYNC {i}] Position closed successfully, stopping polling.")
                break

            if sync_after.get("pending_order") is None:
                print(f"[SYNC {i}] No pending orders, stopping polling.")
                break

        return {
            "ok": True,
            "reason": "close_sent",
            "result": result,
            "sync_after": sync_after,
            "position_closed": not current_position,
        }

    except Exception as e:
        return {
            "ok": False,
            "reason": "execution_error",
            "message": str(e),
        }


async def run_from_bot_state():
    ensure_state_files()
    trading_state, bot_state = load_states()

    client, api_client, order_api, auth_token = build_client()

    try:
        sync_before = await sync_lighter_state(order_api, auth_token)
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
                    sync_after_close = await sync_lighter_state(order_api, auth_token)
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

        sync_after = await sync_lighter_state(order_api, auth_token)
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

    client = None
    api_client = None

    try:
        client, api_client, order_api, auth_token = build_client()

        sync = await sync_lighter_state(order_api, auth_token)

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
                "close_reason": open_order.get("close_reason"),
                "pnl": open_order.get("pnl"),
                "exit_price": open_order.get("exit_price"),
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
        if api_client is not None:
            await api_client.close()
        if client is not None:
            await client.close()


if __name__ == "__main__":
    result = asyncio.run(run_from_bot_state())
    print(result)