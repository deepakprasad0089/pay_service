import json
from datetime import datetime
from db import SessionLocal
from models import Event, Merchant, Transaction


def run():
    db = SessionLocal()

    try:
        with open("sample_events.json") as f:
            data = json.load(f)

        for e in data:
            m = db.get(Merchant, e["merchant_id"])
            if not m:
                db.add(Merchant(
                    id=e["merchant_id"],
                    name=e["merchant_name"]
                ))

            t = db.get(Transaction, e["transaction_id"])
            if not t:
                db.add(Transaction(
                    id=e["transaction_id"],
                    merchant_id=e["merchant_id"],
                    amount=e["amount"],
                    currency=e["currency"],
                    status=e["event_type"]
                ))

            exists = db.query(Event).filter_by(
                transaction_id=e["transaction_id"],
                event_type=e["event_type"]
            ).first()

            if exists:
                continue

            db.add(Event(
                event_id=e["event_id"],
                transaction_id=e["transaction_id"],
                merchant_id=e["merchant_id"],
                event_type=e["event_type"],
                amount=e["amount"],
                currency=e["currency"],
                timestamp=datetime.fromisoformat(e["timestamp"])
            ))

        db.commit()
        print("seed done")

    except Exception as e:
        db.rollback()
        print(e)

    finally:
        db.close()