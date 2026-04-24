import base64
import json
from datetime import datetime

def encode_cursor(dt, id):
    payload = {
        "created_at": dt.isoformat() if dt else None,
        "id": id
    }
    raw = json.dumps(payload).encode()
    return base64.urlsafe_b64encode(raw).decode()

def decode_cursor(cursor):
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
        payload = json.loads(decoded)

        dt = datetime.fromisoformat(payload["created_at"])
        id = payload["id"]

        return dt, id
    except:
        return None, None



def validate_event(data):
    required = [
        "event_type", "transaction_id",
        "merchant_id", "merchant_name",
        "amount", "currency"
    ]

    for f in required:
        if f not in data:
            return f"{f} is required"

    if not isinstance(data["amount"], (int, float)) or data["amount"] <= 0:
        return "amount must be positive number"

    if not isinstance(data["currency"], str) or len(data["currency"]) != 3:
        return "currency must be 3-letter code"

    allowed = {
        "payment_initiated",
        "payment_processed",
        "payment_failed",
        "settled"
    }

    if data["event_type"] not in allowed:
        return "invalid event_type"

    return None