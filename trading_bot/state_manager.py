import os
import json
import time

TRADING_STATE_PATH = "trading_state.json"
BOT_STATE_PATH = "bot_state.json"

def to_jsonable(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, tuple):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if hasattr(obj, "to_dict"):
        try:
            return to_jsonable(obj.to_dict())
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return to_jsonable(vars(obj))
        except Exception:
            pass
    return str(obj)

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        broken_path = path + ".broken"
        try:
            os.replace(path, broken_path)
        except Exception:
            pass
        return default

def save_json(path, data):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(to_jsonable(data), f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def ensure_state_files():
    trading_state = load_json(TRADING_STATE_PATH, {"capital": 10000, "orders": []})
    bot_state = load_json(BOT_STATE_PATH, {
        "symbol": None,
        "timeframe": None,
        "current_position": None,
        "pending_order": None,
        "analyses": [],
        "journal": [],
    })
    save_json(TRADING_STATE_PATH, trading_state)
    save_json(BOT_STATE_PATH, bot_state)


def load_states():
    trading_state = load_json(TRADING_STATE_PATH, {"capital": 10000, "orders": []})
    bot_state = load_json(BOT_STATE_PATH, {
        "symbol": None,
        "timeframe": None,
        "current_position": None,
        "pending_order": None,
        "analyses": [],
        "journal": [],
    })
    return trading_state, bot_state


def save_states(trading_state, bot_state):
    save_json(TRADING_STATE_PATH, trading_state)
    save_json(BOT_STATE_PATH, bot_state)


def append_journal(bot_state, action, details=None, result=None):
    bot_state.setdefault("journal", [])
    bot_state["journal"].append({
        "timestamp": time.time(),
        "action": action,
        "details": details or {},
        "result": result
    })


def next_order_id(trading_state):
    max_id = 0
    for o in trading_state.get("orders", []):
        oid = o.get("id", "")
        if oid.startswith("ORD_"):
            try:
                max_id = max(max_id, int(oid.split("_")[1]))
            except Exception:
                pass
    return f"ORD_{max_id + 1:06d}"


def get_open_logical_order(trading_state, bot_state):
    order_id = bot_state.get("pending_order")
    current_position = bot_state.get("current_position")

    if not order_id and isinstance(current_position, dict):
        order_id = current_position.get("order_id")

    if order_id:
        for order in trading_state.get("orders", []):
            if order.get("id") == order_id:
                return order

    for order in reversed(trading_state.get("orders", [])):
        if order.get("status") in ("pending", "open", "tp1_hit", "partially_open"):
            return order

    return None


def build_current_position_payload(order, current_size):
    return {
        "order_id": order["id"],
        "symbol": order["symbol"],
        "side": order["side"],
        "entry_price": order.get("filled_price") or order.get("price"),
        "size": current_size,
        "tp1": order.get("tp1"),
        "tp2": order.get("tp2"),
        "sl": order.get("sl"),
    }


def should_force_close(order, now_ts=None):
    now_ts = now_ts or time.time()
    filled_at = order.get("filled_at")
    timeout_minutes = order.get("timeout_minutes")
    if not filled_at or not timeout_minutes:
        return False
    return (now_ts - filled_at) >= timeout_minutes * 60


def get_last_trade_signal(bot_state):
    analyses = bot_state.get("analyses", [])
    for a in reversed(analyses):
        if a.get("trade_possible") and a.get("direction") in ("LONG", "SHORT"):
            if all(a.get(k) is not None for k in ("entry_price", "tp1", "tp2", "sl")):
                return {
                    "symbol": bot_state.get("symbol"),
                    "side": a["direction"],
                    "entry_price": float(a["entry_price"]),
                    "tp1": float(a["tp1"]),
                    "tp2": float(a["tp2"]),
                    "sl": float(a["sl"]),
                    "confidence": a.get("confidence"),
                    "reason_code": a.get("reason_code"),
                    "timestamp": a.get("timestamp"),
                }
    return None