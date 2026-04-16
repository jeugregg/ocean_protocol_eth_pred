import os
import math
import time
import requests
import lighter

from dotenv import load_dotenv, find_dotenv
from lighter.signer_client import CreateOrderTxReq

from state_manager import (
    load_states,
    save_states,
    append_journal,
    next_order_id,
    get_open_logical_order,
    build_current_position_payload,
)

load_dotenv(find_dotenv())

BASE_URL = os.getenv("LIGHTER_BASE_URL")
ACCOUNT_INDEX = int(os.getenv("LIGHTER_ACCOUNT_INDEX"))
PRIVATE_KEY = os.getenv("LIGHTER_API_KEY")
API_KEY_INDEX = int(os.getenv("LIGHTER_API_KEY_INDEX"))

MARKETS_URL = "https://explorer.elliot.ai/api/markets"

SYMBOL_TO_LIGHTER = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "BTC": "BTC",
    "ETH": "ETH",
}

PRICE_SCALE = 100.0
BASE_SCALE = 10000.0


def px_to_int(price_float):
    return int(round(float(price_float) * PRICE_SCALE))


def px_to_float(price_int):
    return float(price_int) / PRICE_SCALE


def qty_to_int(size_float):
    return int(round(float(size_float) * BASE_SCALE))


def qty_to_float(size_int):
    return float(size_int) / BASE_SCALE


def approx_equal(a, b, rel_tol=0.02, abs_tol=1e-12):
    return math.isclose(float(a), float(b), rel_tol=rel_tol, abs_tol=abs_tol)


def side_to_position_sign(side):
    return 1 if str(side).upper() == "LONG" else -1


def normalize_symbol(symbol):
    s = (symbol or "").upper().replace("/", "").strip()
    if s in SYMBOL_TO_LIGHTER:
        return SYMBOL_TO_LIGHTER[s]
    s = s.replace("USDT", "").replace("USD", "")
    return s


def get_market_id(symbol):
    lighter_symbol = normalize_symbol(symbol)
    response = requests.get(MARKETS_URL, headers={"accept": "application/json"}, timeout=10)
    response.raise_for_status()
    markets = response.json()
    for m in markets:
        if m["symbol"].upper() == lighter_symbol:
            return int(m["market_index"])
    raise ValueError(f"market_index introuvable pour {symbol} -> {lighter_symbol}")


def build_client():
    client = lighter.SignerClient(
        url=BASE_URL,
        api_private_keys={API_KEY_INDEX: PRIVATE_KEY},
        account_index=ACCOUNT_INDEX,
    )
    api_client = client.api_client
    client.check_client()
    return client, api_client

def normalize_tx_hash(tx_obj):
    if tx_obj is None:
        return None
    if isinstance(tx_obj, str):
        return tx_obj
    if hasattr(tx_obj, "tx_hash"):
        return str(tx_obj.tx_hash)
    return str(tx_obj)

async def fetch_lighter_snapshot(api_client, account_index=ACCOUNT_INDEX):
    account_api = lighter.AccountApi(api_client)
    account_info = await account_api.account(by="index", value=str(account_index))
    account_obj = account_info.accounts[0]

    positions = []
    for p in getattr(account_obj, "positions", []) or []:
        try:
            raw_pos = float(p.position)
        except Exception:
            continue
        if abs(raw_pos) > 1e-12:
            positions.append({
                "raw": p,
                "size": raw_pos,
                "market_id": getattr(p, "market_id", None),
                "entry_price": getattr(p, "entry_price", None),
            })

    active_orders = []
    active_orders_error = None

    try:
        resp = await account_api.account_active_orders(account_index=account_index)
        active_orders = list(getattr(resp, "orders", []) or [])
    except Exception as e1:
        try:
            resp = await account_api.account_active_orders(by="index", value=str(account_index))
            active_orders = list(getattr(resp, "orders", []) or [])
        except Exception as e2:
            active_orders_error = f"{e1} | {e2}"

    return {
        "positions": positions,
        "active_orders": active_orders,
        "active_orders_error": active_orders_error,
    }


def extract_position_size_for_order(snapshot_positions, logical_order):
    expected_sign = side_to_position_sign(logical_order["side"])
    total = 0.0
    for p in snapshot_positions:
        size = float(p["size"])
        if expected_sign > 0 and size > 0:
            total += size
        elif expected_sign < 0 and size < 0:
            total += abs(size)
    return total


def classify_active_orders(active_orders, logical_order):
    entry = float(logical_order["price"])
    tp1 = float(logical_order["tp1"])
    tp2 = float(logical_order["tp2"])
    sl = float(logical_order["sl"])

    out = {"entries": [], "tp1": [], "tp2": [], "sl": [], "other": []}

    for o in active_orders:
        reduce_only = bool(getattr(o, "reduce_only", False))
        price = getattr(o, "price", None)
        trigger_price = getattr(o, "trigger_price", None)

        price_f = px_to_float(price) if price is not None else None
        trigger_f = px_to_float(trigger_price) if trigger_price is not None else None

        matched = False

        if not reduce_only and price_f is not None and approx_equal(price_f, entry, rel_tol=0.003):
            out["entries"].append(o)
            matched = True

        if reduce_only and trigger_f is not None:
            if approx_equal(trigger_f, tp1, rel_tol=0.003):
                out["tp1"].append(o)
                matched = True
            elif approx_equal(trigger_f, tp2, rel_tol=0.003):
                out["tp2"].append(o)
                matched = True
            elif approx_equal(trigger_f, sl, rel_tol=0.003):
                out["sl"].append(o)
                matched = True

        if not matched:
            out["other"].append(o)

    return out


async def sync_lighter_state(api_client, account_index=ACCOUNT_INDEX):
    PENDING_GRACE_SECONDS = 15

    trading_state, bot_state = load_states()
    order = get_open_logical_order(trading_state, bot_state)

    snapshot = await fetch_lighter_snapshot(api_client, account_index)

    if snapshot["active_orders_error"]:
        append_journal(bot_state, "SYNC_WARNING", {"error": snapshot["active_orders_error"]})

    if not order:
        save_states(trading_state, bot_state)
        return {
            "positions_count": len(snapshot["positions"]),
            "active_orders_count": len(snapshot["active_orders"]),
            "pending_order": bot_state.get("pending_order"),
            "current_position": bot_state.get("current_position"),
        }

    now = time.time()
    current_size = extract_position_size_for_order(snapshot["positions"], order)
    expected_size = float(order["size"])
    half_size = expected_size * 0.5

    active_map = classify_active_orders(snapshot["active_orders"], order)

    order.setdefault("exchange", {})
    order["exchange"]["broker"] = "lighter"
    order["exchange"]["last_sync_at"] = now
    order["exchange"]["last_seen_position_size"] = current_size
    order["exchange"]["active_entry_orders"] = len(active_map["entries"])
    order["exchange"]["active_tp1_orders"] = len(active_map["tp1"])
    order["exchange"]["active_tp2_orders"] = len(active_map["tp2"])
    order["exchange"]["active_sl_orders"] = len(active_map["sl"])

    prev_status = order.get("status")
    created_at = float(order.get("created_at", now))
    filled_at = order.get("filled_at")

    no_active_orders = (
        len(active_map["entries"]) == 0
        and len(active_map["tp1"]) == 0
        and len(active_map["tp2"]) == 0
        and len(active_map["sl"]) == 0
    )

    just_created = (now - created_at) < PENDING_GRACE_SECONDS
    never_filled = filled_at is None

    if current_size <= 1e-12:
        if len(active_map["entries"]) > 0:
            order["status"] = "pending"
            bot_state["pending_order"] = order["id"]
            bot_state["current_position"] = None

        elif no_active_orders and never_filled and just_created:
            order["status"] = "pending"
            bot_state["pending_order"] = order["id"]
            bot_state["current_position"] = None

        elif no_active_orders:
            if prev_status in ("open", "tp1_hit", "partially_open"):
                order["status"] = "closed"
                order["closed_at"] = order.get("closed_at") or now
                order["close_reason"] = order.get("close_reason") or "UNKNOWN"
                append_journal(bot_state, "POSITION_CLOSED", {
                    "order_id": order["id"],
                    "close_reason": order["close_reason"]
                })
                bot_state["pending_order"] = None
                bot_state["current_position"] = None
            else:
                order["status"] = "pending"
                bot_state["pending_order"] = order["id"]
                bot_state["current_position"] = None

        else:
            order["status"] = "pending"
            bot_state["pending_order"] = order["id"]
            bot_state["current_position"] = None

    else:
        if order.get("filled_at") is None:
            order["filled_at"] = now
        if order.get("filled_price") is None:
            order["filled_price"] = order.get("price")

        if approx_equal(current_size, expected_size, rel_tol=0.10):
            new_status = "open"
        elif approx_equal(current_size, half_size, rel_tol=0.20) or current_size < expected_size * 0.75:
            new_status = "tp1_hit"
        else:
            new_status = "partially_open"

        if prev_status != new_status:
            if new_status == "open":
                append_journal(bot_state, "POSITION_OPENED", {
                    "order_id": order["id"],
                    "size": current_size
                })
            elif new_status == "tp1_hit":
                append_journal(bot_state, "TP1_DETECTED", {
                    "order_id": order["id"],
                    "remaining_size": current_size
                })

        order["status"] = new_status
        bot_state["pending_order"] = None
        bot_state["current_position"] = build_current_position_payload(order, current_size)

    save_states(trading_state, bot_state)

    return {
        "positions_count": len(snapshot["positions"]),
        "active_orders_count": len(snapshot["active_orders"]),
        "pending_order": bot_state.get("pending_order"),
        "current_position": bot_state.get("current_position"),
    }



async def place_trade_on_lighter(
    client,
    api_client,
    symbol,
    side,
    entry_price,
    tp1,
    tp2,
    sl,
    size,
    timeout_minutes=360,
    order_type="limit",
    entry_slippage=0.0,
    exit_slippage=0.01,
):
    trading_state, bot_state = load_states()

    current_open = get_open_logical_order(trading_state, bot_state)
    if current_open:
        raise Exception(f"Ordre logique déjà vivant: {current_open['id']}")

    market_id = get_market_id(symbol)
    order_id = next_order_id(trading_state)
    now = time.time()

    side = side.upper()
    is_long = side == "LONG"
    entry_is_ask = 0 if is_long else 1
    exit_is_ask = 1 if is_long else 0

    total_size_int = qty_to_int(size)
    qty_1 = total_size_int // 2
    qty_2 = total_size_int - qty_1

    if order_type.lower() != "limit":
        raise NotImplementedError("Cette version splitée gère le parent LIMIT.")

    entry_price_adj = entry_price
    if is_long and entry_slippage > 0:
        entry_price_adj = entry_price * (1 + entry_slippage)
    elif (not is_long) and entry_slippage > 0:
        entry_price_adj = entry_price * (1 - entry_slippage)

    if is_long:
        tp1_limit = tp1 * (1 - exit_slippage)
        tp2_limit = tp2 * (1 - exit_slippage)
        sl_limit = sl * (1 - exit_slippage)
    else:
        tp1_limit = tp1 * (1 + exit_slippage)
        tp2_limit = tp2 * (1 + exit_slippage)
        sl_limit = sl * (1 + exit_slippage)

    logical_order = {
        "id": order_id,
        "symbol": symbol,
        "side": side,
        "order_type": "limit",
        "price": float(entry_price),
        "size": float(size),
        "status": "pending",
        "tp1": float(tp1),
        "tp2": float(tp2),
        "sl": float(sl),
        "timeout_minutes": int(timeout_minutes),
        "created_at": now,
        "filled_at": None,
        "filled_price": None,
        "closed_at": None,
        "close_reason": None,
        "pnl": None,
        "exchange": {
            "broker": "lighter",
            "market_index": market_id,
            "groups": 2,
            "group_tx_hashes": [],
            "last_sync_at": None,
            "last_seen_position_size": 0.0,
        }
    }

    trading_state.setdefault("orders", []).append(logical_order)
    bot_state["symbol"] = symbol
    bot_state["pending_order"] = order_id
    bot_state["current_position"] = None

    append_journal(bot_state, "ORDER_PLACED", {
        "order_id": order_id,
        "symbol": symbol,
        "side": side,
        "entry": float(entry_price),
        "tp1": float(tp1),
        "tp2": float(tp2),
        "sl": float(sl),
        "size": float(size),
    })

    save_states(trading_state, bot_state)

    grouping_type = client.GROUPING_TYPE_ONE_TRIGGERS_A_ONE_CANCELS_THE_OTHER
    tif = client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME

    entry_1 = CreateOrderTxReq(
        MarketIndex=market_id,
        ClientOrderIndex=0,
        BaseAmount=qty_1,
        Price=px_to_int(entry_price_adj),
        IsAsk=entry_is_ask,
        Type=client.ORDER_TYPE_LIMIT,
        TimeInForce=tif,
        ReduceOnly=0,
        TriggerPrice=0,
        OrderExpiry=-1,
    )

    tp_1 = CreateOrderTxReq(
        MarketIndex=market_id,
        ClientOrderIndex=0,
        BaseAmount=0,
        Price=px_to_int(tp1_limit),
        IsAsk=exit_is_ask,
        Type=client.ORDER_TYPE_TAKE_PROFIT_LIMIT,
        TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        ReduceOnly=1,
        TriggerPrice=px_to_int(tp1),
        OrderExpiry=-1,
    )

    sl_1 = CreateOrderTxReq(
        MarketIndex=market_id,
        ClientOrderIndex=0,
        BaseAmount=0,
        Price=px_to_int(sl_limit),
        IsAsk=exit_is_ask,
        Type=client.ORDER_TYPE_STOP_LOSS_LIMIT,
        TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        ReduceOnly=1,
        TriggerPrice=px_to_int(sl),
        OrderExpiry=-1,
    )

    entry_2 = CreateOrderTxReq(
        MarketIndex=market_id,
        ClientOrderIndex=0,
        BaseAmount=qty_2,
        Price=px_to_int(entry_price_adj),
        IsAsk=entry_is_ask,
        Type=client.ORDER_TYPE_LIMIT,
        TimeInForce=tif,
        ReduceOnly=0,
        TriggerPrice=0,
        OrderExpiry=-1,
    )

    tp_2 = CreateOrderTxReq(
        MarketIndex=market_id,
        ClientOrderIndex=0,
        BaseAmount=0,
        Price=px_to_int(tp2_limit),
        IsAsk=exit_is_ask,
        Type=client.ORDER_TYPE_TAKE_PROFIT_LIMIT,
        TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        ReduceOnly=1,
        TriggerPrice=px_to_int(tp2),
        OrderExpiry=-1,
    )

    sl_2 = CreateOrderTxReq(
        MarketIndex=market_id,
        ClientOrderIndex=0,
        BaseAmount=0,
        Price=px_to_int(sl_limit),
        IsAsk=exit_is_ask,
        Type=client.ORDER_TYPE_STOP_LOSS_LIMIT,
        TimeInForce=client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        ReduceOnly=1,
        TriggerPrice=px_to_int(sl),
        OrderExpiry=-1,
    )

    tx1, tx_hash1, err1 = await client.create_grouped_orders(
        grouping_type=grouping_type,
        orders=[entry_1, tp_1, sl_1],
    )

    tx_hash1_norm = normalize_tx_hash(tx_hash1)

    if err1 is not None:
        trading_state, bot_state = load_states()
        order = get_open_logical_order(trading_state, bot_state)
        if order and order["id"] == order_id:
            order["status"] = "error"
        append_journal(bot_state, "ORDER_ERROR", {
            "order_id": order_id,
            "error": str(err1),
            "tx_hash1": tx_hash1_norm,
        })
        save_states(trading_state, bot_state)
        raise Exception(f"Groupe 1 error: {err1}")

    tx2, tx_hash2, err2 = await client.create_grouped_orders(
        grouping_type=grouping_type,
        orders=[entry_2, tp_2, sl_2],
    )

    tx_hash2_norm = normalize_tx_hash(tx_hash2)

    if err2 is not None:
        trading_state, bot_state = load_states()
        order = get_open_logical_order(trading_state, bot_state)
        if order and order["id"] == order_id:
            order["status"] = "error"
        append_journal(bot_state, "ORDER_ERROR", {
            "order_id": order_id,
            "error": str(err2),
            "partial": True,
            "tx_hash1": tx_hash1_norm,
            "tx_hash2": tx_hash2_norm,
        })
        save_states(trading_state, bot_state)
        raise Exception(f"Groupe 2 error: {err2}")

    trading_state, bot_state = load_states()
    order = get_open_logical_order(trading_state, bot_state)

    if order and order["id"] == order_id:
        order["status"] = "pending"
        order["exchange"]["group_tx_hashes"] = [tx_hash1_norm, tx_hash2_norm]
        order["exchange"]["qty_1"] = qty_to_float(qty_1)
        order["exchange"]["qty_2"] = qty_to_float(qty_2)
        order["exchange"]["entry_price_sent"] = float(entry_price_adj)
        order["exchange"]["last_submit_at"] = time.time()

    append_journal(bot_state, "LIGHTER_GROUPS_SENT", {
        "order_id": order_id,
        "tx_hashes": [tx_hash1_norm, tx_hash2_norm],
    })

    save_states(trading_state, bot_state)

    sync_result = await sync_lighter_state(api_client, ACCOUNT_INDEX)

    return {
        "order_id": order_id,
        "tx_hash1": tx_hash1_norm,
        "tx_hash2": tx_hash2_norm,
        "sync": sync_result,
    }


async def close_position_market(client, api_client, symbol, side, size, worst_slippage=0.02):
    market_id = get_market_id(symbol)
    res_ob = await client.order_api.order_book_details(market_id=market_id)
    last_trade_price = float(res_ob.order_book_details[0].last_trade_price)

    is_long = side.upper() == "LONG"
    is_ask = 1 if is_long else 0

    if is_ask:
        worst_price = last_trade_price * (1 - worst_slippage)
    else:
        worst_price = last_trade_price * (1 + worst_slippage)

    tx, tx_hash, err = await client.create_market_order(
        market_index=market_id,
        client_order_index=0,
        base_amount=qty_to_int(size),
        avg_execution_price=px_to_int(worst_price),
        is_ask=is_ask,
    )
    if err is not None:
        raise Exception(err)

    trading_state, bot_state = load_states()
    order = get_open_logical_order(trading_state, bot_state)
    if order:
        order["close_reason"] = "TIMEOUT"
        append_journal(bot_state, "FORCE_CLOSE_SENT", {
            "order_id": order["id"],
            "tx_hash": str(tx_hash)
        })
        save_states(trading_state, bot_state)

    return tx, tx_hash, err