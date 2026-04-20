import os
import math
import time
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

ACCOUNT_INDEX = int(os.getenv("LIGHTER_ACCOUNT_INDEX"))
PRIVATE_KEY = os.getenv("LIGHTER_API_KEY")
API_KEY_INDEX = int(os.getenv("LIGHTER_API_KEY_INDEX"))
BASE_URL = os.getenv("LIGHTER_BASE_URL", "").rstrip("/")

SYMBOL_ALIASES = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "BTC": "BTC",
    "ETH": "ETH",
}

PRICE_SCALE = 100.0
BASE_SCALE = 10000.0
EPS = 1e-12


def px_to_int(price_float):
    return int(round(float(price_float) * PRICE_SCALE))


def px_to_float(price_int):
    return float(price_int) / PRICE_SCALE


def qty_to_int(size_float):
    return int(round(float(size_float) * BASE_SCALE))


def qty_to_float(size_int):
    return float(size_int) / BASE_SCALE


def now_s():
    return time.time()


def now_ms():
    return int(time.time() * 1000)


def approx_equal(a, b, rel_tol=0.003, abs_tol=1e-12):
    try:
        return math.isclose(float(a), float(b), rel_tol=rel_tol, abs_tol=abs_tol)
    except Exception:
        return False


def normalize_symbol(symbol):
    s = (symbol or "").upper().replace("/", "").strip()
    if s in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[s]
    s = s.replace("USDT", "").replace("USD", "")
    return s


def side_sign(side):
    return 1 if str(side).upper() == "LONG" else -1


def _to_plain(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_to_plain(x) for x in obj]
    if isinstance(obj, tuple):
        return [_to_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_plain(v) for k, v in obj.items()}
    if hasattr(obj, "to_dict"):
        try:
            return _to_plain(obj.to_dict())
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return _to_plain(vars(obj))
        except Exception:
            pass
    return str(obj)


def _obj_get(obj, *keys, default=None):
    for key in keys:
        if isinstance(obj, dict) and key in obj:
            return obj[key]
        if hasattr(obj, key):
            return getattr(obj, key)
    return default


def _extract_list(resp, candidate_keys):
    plain = _to_plain(resp)

    if isinstance(plain, list):
        return plain

    if isinstance(plain, dict):
        for key in candidate_keys:
            val = plain.get(key)
            if isinstance(val, list):
                return val

        data = plain.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in candidate_keys:
                val = data.get(key)
                if isinstance(val, list):
                    return val

    for key in candidate_keys:
        try:
            val = getattr(resp, key)
            if isinstance(val, list):
                return [_to_plain(x) for x in val]
        except Exception:
            pass

    return []


def _normalize_ts(value):
    if value is None:
        return None
    try:
        x = float(value)
    except Exception:
        return None
    if x > 1e12:
        return x / 1000.0
    if x > 1e10:
        return x / 1000.0
    return x


def _normalize_price(value):
    if value is None:
        return None
    try:
        x = float(value)
        if x > 100000:
            return px_to_float(x)
        return x
    except Exception:
        return None


def _normalize_size(value):
    if value is None:
        return None
    try:
        x = float(value)
        if x > 1000:
            return qty_to_float(x)
        return x
    except Exception:
        return None


def normalize_tx_hash(tx_obj):
    if tx_obj is None:
        return None
    if isinstance(tx_obj, str):
        return tx_obj
    if hasattr(tx_obj, "tx_hash"):
        return str(tx_obj.tx_hash)
    return str(tx_obj)


def build_client():
    client = lighter.SignerClient(
        url=BASE_URL,
        api_private_keys={API_KEY_INDEX: PRIVATE_KEY},
        account_index=ACCOUNT_INDEX,
    )
    client.check_client()
    api_client = client.api_client
    order_api = lighter.OrderApi(api_client)
    auth_token, err = client.create_auth_token_with_expiry(3600)
    if err:
        raise Exception(f"Auth token failed: {err}") 
    return client, api_client, order_api, auth_token


async def get_market_id(order_api, symbol):
    env_key = f"LIGHTER_MARKET_ID_{symbol.upper()}"
    env_val = os.getenv(env_key)
    if env_val:
        return int(env_val)

    target = normalize_symbol(symbol)

    resp = await order_api.order_book_details(filter="perp")
    rows = _extract_list(resp, [
        "order_book_details",
    ])

    if not rows:
        rows = [_to_plain(resp)]

    for row in rows:
        sym = str(_obj_get(row, "symbol", "name", "ticker", default="")).upper()
        market_id = _obj_get(row, "market_id", "marketid", "marketIndex", "market_index")
        if market_id is None:
            continue

        sym_clean = sym.replace("/", "").replace("-PERP", "").replace("USDT", "").replace("USD", "")
        if sym_clean == target:
            return int(market_id)

    raise ValueError(
        f"Impossible de résoudre market_id pour {symbol}. "
        f"Ajoute LIGHTER_MARKET_ID_{symbol.upper()} dans l'env si besoin."
    )


async def fetch_market_meta(order_api, market_id=None, symbol=None):
    if market_id is not None:
        resp = await order_api.order_book_details(market_id=int(market_id))
    else:
        resp = await order_api.order_book_details(filter=normalize_symbol(symbol))
    return _to_plain(resp)


async def fetch_active_orders(order_api, account_index, market_id, auth_token):
    resp = await order_api.account_active_orders(
        account_index=int(account_index),
        market_id=int(market_id),
        auth=auth_token,
    )
    return _extract_list(resp, ["orders", "data", "items", "result"])


async def fetch_inactive_orders(order_api, account_index, market_id, auth_token, limit=100, since_ms=None):
    kwargs = {
        "account_index": int(account_index),
        "limit": min(int(limit), 100),
        "market_id": int(market_id),
        "auth": auth_token,
    }
    if since_ms is not None:
        kwargs["between_timestamps"] = f"{int(since_ms)},{now_ms()}"

    try:
        resp = await order_api.account_inactive_orders(**kwargs)
    except Exception:
        kwargs.pop("between_timestamps", None)
        resp = await order_api.account_inactive_orders(**kwargs)

    return _extract_list(resp, ["orders", "data", "items", "result"])


async def fetch_trades(
    order_api,
    account_index,
    market_id,
    auth_token,
    limit=100,
    sort_by="timestamp",
    sort_dir="desc",
    since_ms=None,
    order_index=None,
):
    kwargs = {
        "sort_by": sort_by,
        "limit": min(int(limit), 100),
        "account_index": int(account_index),
        "market_id": int(market_id),
        "sort_dir": sort_dir,
        "auth": auth_token,
    }
    if since_ms is not None:
        kwargs["var_from"] = int(since_ms)
    if order_index is not None:
        kwargs["order_index"] = int(order_index)

    resp = await order_api.trades(**kwargs)
    return _extract_list(resp, ["trades", "data", "items", "result"])


def _to_float_or_none(v):
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _parse_trade_row(row, my_account_id=ACCOUNT_INDEX):
    my_account_id = int(my_account_id)

    price = _normalize_price(_obj_get(row, "price", "execution_price", "executionPrice"))
    size = _normalize_size(_obj_get(row, "size", "base_amount", "baseAmount", "amount", "qty", "quantity"))
    timestamp = _normalize_ts(_obj_get(row, "timestamp", "created_at", "createdAt", "time"))
    market_id = _obj_get(row, "market_id", "marketid", "marketIndex", "market_index")

    ask_account_id = _obj_get(row, "ask_account_id", "askAccountId")
    bid_account_id = _obj_get(row, "bid_account_id", "bidAccountId")

    ask_id = _obj_get(row, "ask_id", "askId")
    bid_id = _obj_get(row, "bid_id", "bidId")

    ask_client_id = _obj_get(row, "ask_client_id", "askClientId")
    bid_client_id = _obj_get(row, "bid_client_id", "bidClientId")

    is_maker_ask = _obj_get(row, "is_maker_ask", "isMakerAsk", default=None)
    if is_maker_ask is not None:
        is_maker_ask = bool(is_maker_ask)

    my_side = None
    is_ask = None
    my_role = None
    my_order_id = None
    my_client_id = None
    my_account_pnl = None
    my_position_size_before = None
    my_entry_quote_before = None

    if ask_account_id is not None and int(ask_account_id) == my_account_id:
        is_ask = True
        my_side = "SELL"
        my_order_id = ask_id
        my_client_id = ask_client_id
        my_account_pnl = _to_float_or_none(_obj_get(row, "ask_account_pnl", "askAccountPnl"))

        if is_maker_ask is not None:
            my_role = "maker" if is_maker_ask else "taker"

    elif bid_account_id is not None and int(bid_account_id) == my_account_id:
        is_ask = False
        my_side = "BUY"
        my_order_id = bid_id
        my_client_id = bid_client_id
        my_account_pnl = _to_float_or_none(_obj_get(row, "bid_account_pnl", "bidAccountPnl"))

        if is_maker_ask is not None:
            my_role = "taker" if is_maker_ask else "maker"

    else:
        side = _obj_get(row, "side", default=None)
        ask_filter = _obj_get(row, "ask_filter", "askFilter", default=None)

        if ask_filter is not None:
            try:
                is_ask = bool(int(ask_filter))
            except Exception:
                pass

        if is_ask is None and side is not None:
            s = str(side).upper()
            if s in ("SELL", "ASK", "SHORT"):
                is_ask = True
            elif s in ("BUY", "BID", "LONG"):
                is_ask = False

        if is_ask is True:
            my_side = "SELL"
        elif is_ask is False:
            my_side = "BUY"

    if my_role == "taker":
        my_position_size_before = _to_float_or_none(
            _obj_get(row, "taker_position_size_before", "takerPositionSizeBefore")
        )
        my_entry_quote_before = _to_float_or_none(
            _obj_get(row, "taker_entry_quote_before", "takerEntryQuoteBefore")
        )
    elif my_role == "maker":
        my_position_size_before = _to_float_or_none(
            _obj_get(row, "maker_position_size_before", "makerPositionSizeBefore")
        )
        my_entry_quote_before = _to_float_or_none(
            _obj_get(row, "maker_entry_quote_before", "makerEntryQuoteBefore")
        )

    my_position_size_after = None
    if my_position_size_before is not None and size is not None and my_side is not None:
        if my_side == "BUY":
            my_position_size_after = my_position_size_before + size
        elif my_side == "SELL":
            my_position_size_after = my_position_size_before - size

    action_hint = None
    if my_position_size_before is not None and size is not None and my_side is not None:
        if my_side == "BUY":
            if my_position_size_before < 0:
                action_hint = "CLOSE_SHORT_OR_REDUCE_SHORT"
            else:
                action_hint = "OPEN_LONG_OR_ADD_LONG"
        elif my_side == "SELL":
            if my_position_size_before > 0:
                action_hint = "CLOSE_LONG_OR_REDUCE_LONG"
            else:
                action_hint = "OPEN_SHORT_OR_ADD_SHORT"

    return {
        "trade_id": _obj_get(row, "trade_id", "tradeId"),
        "tx_hash": _obj_get(row, "tx_hash", "txHash"),
        "price": price,
        "size": size,
        "timestamp": timestamp,
        "market_id": market_id,

        "order_index": _obj_get(row, "order_index", "orderIndex"),
        "type": _obj_get(row, "type", default=None),

        "ask_account_id": ask_account_id,
        "bid_account_id": bid_account_id,
        "ask_id": ask_id,
        "bid_id": bid_id,
        "ask_client_id": ask_client_id,
        "bid_client_id": bid_client_id,
        "is_maker_ask": is_maker_ask,

        "side": my_side,
        "is_ask": is_ask,
        "is_buy": (is_ask is False) if is_ask is not None else None,
        "is_sell": (is_ask is True) if is_ask is not None else None,

        "my_account_id": my_account_id,
        "my_order_id": my_order_id,
        "my_client_id": my_client_id,
        "my_role": my_role,
        "my_account_pnl": my_account_pnl,
        "my_position_size_before": my_position_size_before,
        "my_entry_quote_before": my_entry_quote_before,
        "my_position_size_after": my_position_size_after,
        "action_hint": action_hint,

        "raw": _to_plain(row),
    }


def _parse_order_row(row):
    return {
        "price": _normalize_price(_obj_get(row, "price")),
        "trigger_price": _normalize_price(_obj_get(row, "trigger_price", "triggerPrice")),
        "size": _normalize_size(_obj_get(row, "size", "base_amount", "baseAmount", "amount", "qty", "quantity")),
        "filled_size": _normalize_size(_obj_get(row, "filled_size", "filledSize", "executed_size", "executedSize")),
        "remaining_size": _normalize_size(_obj_get(row, "remaining_size", "remainingSize", "resting_size", "restingSize")),
        "is_ask": _obj_get(row, "is_ask", "isAsk", default=None),
        "reduce_only": bool(_obj_get(row, "reduce_only", "reduceOnly", default=False)),
        "status": str(_obj_get(row, "status", "state", "order_status", "orderStatus", default="")),
        "type": str(_obj_get(row, "type", default="")),
        "timestamp": _normalize_ts(_obj_get(row, "timestamp", "created_at", "createdAt", "updated_at", "updatedAt", "time")),
        "market_id": _obj_get(row, "market_id", "marketid", "marketIndex", "market_index"),
        "order_index": _obj_get(row, "order_index", "orderIndex"),
        "raw": _to_plain(row),
    }


def _trade_is_buy(tr):
    if tr["is_ask"] is None:
        return None
    return not bool(tr["is_ask"])


def _trade_is_sell(tr):
    if tr["is_ask"] is None:
        return None
    return bool(tr["is_ask"])


def _price_near_any(price, prices, rel_tol=0.003):
    return any(p is not None and price is not None and approx_equal(price, p, rel_tol=rel_tol) for p in prices)


def _is_entry_trade(order, tr):
    side = str(order["side"]).upper()
    hint = tr.get("action_hint")

    if side == "LONG":
        return hint == "OPEN_LONG_OR_ADD_LONG"
    if side == "SHORT":
        return hint == "OPEN_SHORT_OR_ADD_SHORT"
    return False


def _is_exit_trade(order, tr):
    side = str(order["side"]).upper()
    hint = tr.get("action_hint")

    if side == "LONG":
        return hint == "CLOSE_LONG_OR_REDUCE_LONG"
    if side == "SHORT":
        return hint == "CLOSE_SHORT_OR_REDUCE_SHORT"
    return False


def _compute_trade_progress(order, trades):
    created_at = float(order.get("created_at") or 0.0)
    parsed = [_parse_trade_row(t) for t in trades]
    parsed = [t for t in parsed if t["timestamp"] is None or (t["timestamp"] >= (created_at - 10))]
    parsed.sort(key=lambda x: (x["timestamp"] or 0))

    entry_fills = [t for t in parsed if _is_entry_trade(order, t)]
    exit_fills = [t for t in parsed if _is_exit_trade(order, t)]

    entry_qty = sum(abs(t["size"]) for t in entry_fills if t["size"] is not None)
    exit_qty = sum(abs(t["size"]) for t in exit_fills if t["size"] is not None)
    open_qty = max(entry_qty - exit_qty, 0.0)

    entry_avg = None
    if entry_qty > EPS:
        entry_avg = sum(t["price"] * abs(t["size"]) for t in entry_fills if t["price"] is not None and t["size"] is not None) / entry_qty

    exit_avg = None
    if exit_qty > EPS:
        exit_avg = sum(t["price"] * abs(t["size"]) for t in exit_fills if t["price"] is not None and t["size"] is not None) / exit_qty

    first_entry_ts = min((t["timestamp"] for t in entry_fills if t["timestamp"] is not None), default=None)
    last_exit_ts = max((t["timestamp"] for t in exit_fills if t["timestamp"] is not None), default=None)

    return {
        "entry_fills": entry_fills,
        "exit_fills": exit_fills,
        "entry_qty": entry_qty,
        "exit_qty": exit_qty,
        "open_qty": open_qty,
        "entry_avg": entry_avg,
        "exit_avg": exit_avg,
        "first_entry_ts": first_entry_ts,
        "last_exit_ts": last_exit_ts,
    }


def _classify_active_orders(order, active_orders):
    entry = float(order["price"])
    tp1 = float(order["tp1"])
    tp2 = float(order["tp2"])
    sl = float(order["sl"])

    result = {"entry": [], "tp1": [], "tp2": [], "sl": [], "other": []}

    for raw in active_orders:
        row = _parse_order_row(raw)
        reduce_only = row["reduce_only"]
        price = row["price"]
        trigger = row["trigger_price"]
        matched = False

        if not reduce_only and price is not None and approx_equal(price, entry, rel_tol=0.004):
            result["entry"].append(row)
            matched = True

        if reduce_only:
            check_val = trigger if trigger is not None else price
            if check_val is not None:
                if approx_equal(check_val, tp1, rel_tol=0.004):
                    result["tp1"].append(row)
                    matched = True
                elif approx_equal(check_val, tp2, rel_tol=0.004):
                    result["tp2"].append(row)
                    matched = True
                elif approx_equal(check_val, sl, rel_tol=0.004):
                    result["sl"].append(row)
                    matched = True

        if not matched:
            result["other"].append(row)

    return result


def _inactive_child_hits(order, inactive_orders):
    tp1 = float(order["tp1"])
    tp2 = float(order["tp2"])
    sl = float(order["sl"])

    out = {
        "tp1_hit": False,
        "tp2_hit": False,
        "sl_hit": False,
        "matched_rows": [],
    }

    for raw in inactive_orders:
        row = _parse_order_row(raw)
        if not row["reduce_only"]:
            continue

        check_val = row["trigger_price"] if row["trigger_price"] is not None else row["price"]
        if check_val is None:
            continue

        executed = False
        if row["filled_size"] is not None and row["filled_size"] > EPS:
            executed = True
        status_up = (row["status"] or "").upper()
        if any(x in status_up for x in ["FILLED", "EXECUTED", "MATCHED", "CLOSED"]):
            executed = True

        if not executed:
            continue

        if approx_equal(check_val, tp1, rel_tol=0.004):
            out["tp1_hit"] = True
            out["matched_rows"].append(row)
        elif approx_equal(check_val, tp2, rel_tol=0.004):
            out["tp2_hit"] = True
            out["matched_rows"].append(row)
        elif approx_equal(check_val, sl, rel_tol=0.004):
            out["sl_hit"] = True
            out["matched_rows"].append(row)

    return out


def _classify_close(order, progress, inactive_orders):
    entry_qty = progress["entry_qty"]
    exit_qty = progress["exit_qty"]
    exit_fills = progress["exit_fills"]
    exit_avg = progress["exit_avg"]
    entry_avg = progress["entry_avg"] or float(order["price"])

    child_hits = _inactive_child_hits(order, inactive_orders)

    saw_tp1_trade = any(approx_equal(t["price"], order["tp1"], rel_tol=0.002) for t in exit_fills if t["price"] is not None)
    saw_tp2_trade = any(approx_equal(t["price"], order["tp2"], rel_tol=0.002) for t in exit_fills if t["price"] is not None)
    saw_sl_trade = any(approx_equal(t["price"], order["sl"], rel_tol=0.002) for t in exit_fills if t["price"] is not None)

    tp1_hit = child_hits["tp1_hit"] or saw_tp1_trade
    tp2_hit = child_hits["tp2_hit"] or saw_tp2_trade
    sl_hit = child_hits["sl_hit"] or saw_sl_trade

    pnl = None
    if exit_avg is not None and exit_qty > EPS:
        if str(order["side"]).upper() == "LONG":
            pnl = (exit_avg - entry_avg) * exit_qty
        else:
            pnl = (entry_avg - exit_avg) * exit_qty

    if entry_qty <= EPS:
        return {
            "close_reason": "NOT_FILLED",
            "pnl": 0.0,
            "exit_price": None,
            "closed_at": order.get("closed_at") or now_s(),
            "realized_qty": 0.0,
        }

    if tp1_hit and sl_hit:
        reason = "TP1_THEN_SL"
    elif sl_hit:
        reason = "STOP_LOSS"
    elif tp2_hit:
        reason = "TAKE_PROFIT"
    elif tp1_hit and exit_qty + EPS >= entry_qty:
        reason = "TAKE_PROFIT"
    elif tp1_hit:
        reason = "PARTIAL_TAKE_PROFIT"
    else:
        if pnl is not None and pnl < 0:
            reason = "LOSS_OTHER"
        elif pnl is not None and pnl > 0:
            reason = "PROFIT_OTHER"
        else:
            reason = "MANUAL_OR_OTHER"

    return {
        "close_reason": reason,
        "pnl": pnl,
        "exit_price": exit_avg,
        "closed_at": progress["last_exit_ts"] or now_s(),
        "realized_qty": exit_qty,
    }


def _pick_order_to_sync(trading_state, bot_state):
    live = get_open_logical_order(trading_state, bot_state)
    if live:
        return live

    for order in reversed(trading_state.get("orders", [])):
        if order.get("filled_at") and (
            order.get("status") in ("open", "tp1_hit", "partially_open")
            or (order.get("status") == "closed" and (order.get("close_reason") in (None, "UNKNOWN") or order.get("pnl") is None))
        ):
            return order

        if order.get("status") in ("pending", "open", "tp1_hit", "partially_open"):
            return order

    return None


async def sync_lighter_state(order_api=None, auth_token=None, account_index=ACCOUNT_INDEX):
    #created_client = False
    #client = None
    #order_api = None

    if order_api is None:
        _, _, order_api, auth_token = build_client()
        #created_client = True
    # else:
    #     order_api = lighter.OrderApi(api_client)

    trading_state, bot_state = load_states()
    order = _pick_order_to_sync(trading_state, bot_state)

    if not order:
        save_states(trading_state, bot_state)
        #if created_client:
        #    await api_client.close()
        #    await client.close()
        return {
            "ok": True,
            "message": "no logical order to sync",
            "pending_order": bot_state.get("pending_order"),
            "current_position": bot_state.get("current_position"),
        }

    market_id = int(order["exchange"]["market_index"])
    since_ms = int((float(order.get("created_at") or now_s()) - 60) * 1000)
    active_orders = await fetch_active_orders(order_api, account_index, market_id, auth_token)
    inactive_orders = await fetch_inactive_orders(order_api, account_index, market_id, auth_token, limit=100, since_ms=since_ms)
    trades = await fetch_trades(
        order_api,
        account_index=account_index,
        market_id=market_id,
        auth_token=auth_token,
        limit=100,
        sort_by="timestamp",
        sort_dir="desc",
        since_ms=None,
    )

    progress = _compute_trade_progress(order, trades)
    active_map = _classify_active_orders(order, active_orders)

    prev_status = order.get("status")
    entry_qty = progress["entry_qty"]
    open_qty = progress["open_qty"]
    expected_qty = float(order["size"])
    half_qty = expected_qty * 0.5

    order.setdefault("exchange", {})
    order["exchange"]["broker"] = "lighter"
    order["exchange"]["market_index"] = market_id
    order["exchange"]["last_sync_at"] = now_s()
    order["exchange"]["active_entry_orders"] = len(active_map["entry"])
    order["exchange"]["active_tp1_orders"] = len(active_map["tp1"])
    order["exchange"]["active_tp2_orders"] = len(active_map["tp2"])
    order["exchange"]["active_sl_orders"] = len(active_map["sl"])
    order["exchange"]["entry_qty_seen"] = entry_qty
    order["exchange"]["exit_qty_seen"] = progress["exit_qty"]
    order["exchange"]["open_qty_seen"] = open_qty

    if entry_qty > EPS:
        if order.get("filled_at") is None:
            order["filled_at"] = progress["first_entry_ts"] or now_s()
        if order.get("filled_price") is None:
            order["filled_price"] = progress["entry_avg"] or order["price"]

    if entry_qty <= EPS:
        if len(active_map["entry"]) > 0:
            order["status"] = "pending"
            bot_state["pending_order"] = order["id"]
            bot_state["current_position"] = None
        else:
            order["status"] = "closed"
            order["closed_at"] = order.get("closed_at") or now_s()
            order["close_reason"] = "NOT_FILLED"
            order["pnl"] = 0.0
            bot_state["pending_order"] = None
            bot_state["current_position"] = None

            if prev_status != "closed":
                append_journal(bot_state, "POSITION_CLOSED", {
                    "order_id": order["id"],
                    "close_reason": order["close_reason"],
                    "pnl": order["pnl"],
                })

    elif open_qty > EPS:
        if open_qty >= expected_qty * 0.90:
            new_status = "open"
        elif open_qty <= half_qty * 1.20:
            new_status = "tp1_hit"
        else:
            new_status = "partially_open"

        order["status"] = new_status
        bot_state["pending_order"] = None
        bot_state["current_position"] = build_current_position_payload(order, open_qty)

        if prev_status != new_status:
            if new_status == "open":
                append_journal(bot_state, "POSITION_OPENED", {
                    "order_id": order["id"],
                    "size": open_qty,
                    "filled_price": order.get("filled_price"),
                })
            elif new_status == "tp1_hit":
                append_journal(bot_state, "TP1_DETECTED", {
                    "order_id": order["id"],
                    "remaining_size": open_qty,
                })

    else:
        close_info = _classify_close(order, progress, inactive_orders)

        order["status"] = "closed"
        order["closed_at"] = close_info["closed_at"] or now_s()
        order["close_reason"] = close_info["close_reason"]
        order["pnl"] = close_info["pnl"]
        order["exit_price"] = close_info["exit_price"]
        order["realized_qty"] = close_info["realized_qty"]

        if order.get("pnl") is not None and not order["exchange"].get("pnl_applied_to_capital"):
            trading_state["capital"] = float(trading_state.get("capital", 0.0)) + float(order["pnl"])
            order["exchange"]["pnl_applied_to_capital"] = True

        bot_state["pending_order"] = None
        bot_state["current_position"] = None

        if prev_status != "closed" or order.get("close_reason") in (None, "UNKNOWN") or order.get("pnl") is None:
            append_journal(bot_state, "POSITION_CLOSED", {
                "order_id": order["id"],
                "close_reason": order["close_reason"],
                "pnl": order.get("pnl"),
                "exit_price": order.get("exit_price"),
            })

    save_states(trading_state, bot_state)

    result = {
        "ok": True,
        "order_id": order["id"],
        "status": order["status"],
        "close_reason": order.get("close_reason"),
        "pnl": order.get("pnl"),
        "entry_qty": entry_qty,
        "open_qty": open_qty,
        "active_orders_count": len(active_orders),
        "inactive_orders_count": len(inactive_orders),
        "trades_count": len(trades),
        "pending_order": bot_state.get("pending_order"),
        "current_position": bot_state.get("current_position"),
    }

    # if created_client:
    #     await api_client.close()
    #     await client.close()

    return result


async def place_trade_on_lighter(
    client,
    api_client,
    order_api,
    auth_token,
    symbol,
    side,
    entry_price,
    tp1,
    tp2,
    sl,
    size,
    timeout_minutes=60,
    order_type="limit",
    entry_slippage=0.0,
    exit_slippage=0.01,
):
    #order_api = lighter.OrderApi(api_client)

    market_id = await get_market_id(order_api, symbol)

    trading_state, bot_state = load_states()

    current_open = get_open_logical_order(trading_state, bot_state)
    if current_open:
        raise Exception(f"Ordre logique déjà vivant: {current_open['id']}")

    order_id = next_order_id(trading_state)
    created_at = now_s()

    side = side.upper()
    is_long = side == "LONG"
    entry_is_ask = 0 if is_long else 1
    exit_is_ask = 1 if is_long else 0

    total_size_int = qty_to_int(size)
    qty_1 = total_size_int // 2
    qty_2 = total_size_int - qty_1

    if order_type.lower() != "limit":
        raise NotImplementedError("Cette version gère le parent LIMIT.")

    entry_price_adj = float(entry_price)
    if entry_slippage > 0:
        entry_price_adj = entry_price * (1 + entry_slippage if is_long else 1 - entry_slippage)

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
        "created_at": created_at,
        "filled_at": None,
        "filled_price": None,
        "closed_at": None,
        "close_reason": None,
        "pnl": None,
        "exit_price": None,
        "realized_qty": None,
        "exchange": {
            "broker": "lighter",
            "market_index": market_id,
            "groups": 2,
            "group_tx_hashes": [],
            "qty_1": qty_to_float(qty_1),
            "qty_2": qty_to_float(qty_2),
            "entry_price_sent": float(entry_price_adj),
            "last_submit_at": None,
            "last_sync_at": None,
            "active_entry_orders": 0,
            "active_tp1_orders": 0,
            "active_tp2_orders": 0,
            "active_sl_orders": 0,
        },
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
        TimeInForce=tif,
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
        TimeInForce=tif,
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
        TimeInForce=tif,
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
        TimeInForce=tif,
        ReduceOnly=1,
        TriggerPrice=px_to_int(sl),
        OrderExpiry=-1,
    )

    tx1, tx_hash1, err1 = await client.create_grouped_orders(
        grouping_type=grouping_type,
        orders=[entry_1, tp_1, sl_1],
    )
    tx_hash1 = normalize_tx_hash(tx_hash1)

    if err1 is not None:
        append_journal(bot_state, "ORDER_ERROR", {
            "order_id": order_id,
            "error": str(err1),
            "tx_hash1": tx_hash1,
        })
        save_states(trading_state, bot_state)
        raise Exception(f"Groupe 1 error: {err1}")

    tx2, tx_hash2, err2 = await client.create_grouped_orders(
        grouping_type=grouping_type,
        orders=[entry_2, tp_2, sl_2],
    )
    tx_hash2 = normalize_tx_hash(tx_hash2)

    if err2 is not None:
        append_journal(bot_state, "ORDER_ERROR", {
            "order_id": order_id,
            "error": str(err2),
            "partial": True,
            "tx_hash1": tx_hash1,
            "tx_hash2": tx_hash2,
        })
        save_states(trading_state, bot_state)
        raise Exception(f"Groupe 2 error: {err2}")

    trading_state, bot_state = load_states()
    order = get_open_logical_order(trading_state, bot_state)

    if order and order["id"] == order_id:
        order["exchange"]["group_tx_hashes"] = [tx_hash1, tx_hash2]
        order["exchange"]["last_submit_at"] = now_s()

    append_journal(bot_state, "LIGHTER_GROUPS_SENT", {
        "order_id": order_id,
        "tx_hashes": [tx_hash1, tx_hash2],
    })

    save_states(trading_state, bot_state)
    time.sleep(3) # waiting for orders to be updated
    sync_result = await sync_lighter_state(order_api, auth_token)

    return {
        "order_id": order_id,
        "tx_hash1": tx_hash1,
        "tx_hash2": tx_hash2,
        "sync": sync_result,
    }


async def close_position_market(client, api_client, symbol, side, size, worst_slippage=0.02):
    order_api = lighter.OrderApi(api_client)
    market_id = await get_market_id(order_api, symbol)

    ob = await order_api.order_book_details(market_id=market_id)
    rows = _extract_list(ob, ["order_book_details", "orderBookDetails", "data", "items"])
    row = rows[0] if rows else _to_plain(ob)

    last_trade_price = _normalize_price(_obj_get(row, "last_trade_price", "lastTradePrice"))
    if last_trade_price is None:
        raise Exception("Impossible de lire last_trade_price via orderbookdetails")

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
        reduce_only=1,  # Safety: prevents opening inverse position
    )

    if err is not None:
        raise Exception(err)

    tx_hash = normalize_tx_hash(tx_hash)

    trading_state, bot_state = load_states()
    order = get_open_logical_order(trading_state, bot_state)
    if order:
        order["close_reason"] = "FORCE_CLOSE_REQUESTED"
        append_journal(bot_state, "FORCE_CLOSE_SENT", {
            "order_id": order["id"],
            "tx_hash": tx_hash,
        })
        save_states(trading_state, bot_state)

    return tx, tx_hash, err