from flask import Flask, request, jsonify
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from flasgger import Swagger
from sqlalchemy import func, and_, or_
from db import SessionLocal
from models import Merchant, Transaction, Event
from datetime import datetime
from  utils import *

app = Flask(__name__)

swagger_template = {
    "info": {
        "title": "Payment API",
        "description": "API documentation",
        "version": "1.0.0"
    },
    "basePath": "/api/v1",
}

swagger = Swagger(app, template=swagger_template)


def get_db():
    return SessionLocal()

def parse_date(dt):
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt)
    except:
        try:
            return datetime.strptime(dt, "%Y-%m-%d")
        except:
            return None



def success(data=None, message=None):
    res = {"data": data}
    if message:
        res["message"] = message
    return jsonify(res), 200


def error(message, code=400):
    return jsonify({
        "error": message
    }), code




# ------------------ CORE LOGIC ------------------

def upsert_merchant(db, data):
    merchant = db.query(Merchant).filter_by(id=data['merchant_id']).first()
    if not merchant:
        try:
            merchant = Merchant(
                id=data['merchant_id'],
                name=data['merchant_name']
            )
            db.add(merchant)
            db.flush()
        except IntegrityError:
            db.rollback()
            merchant = db.query(Merchant).filter_by(id=data['merchant_id']).first()
    return merchant

def is_valid_transition(old, new):
    transitions = {
        "payment_initiated": {"payment_processed"},
        "payment_processed": {"settled", "payment_failed"},
        "settled": set(),
        "payment_failed": set()
    }

    return new in transitions.get(old, set())


def upsert_transaction(db, data):
    txn = db.query(Transaction).filter_by(id=data['transaction_id']).first()

    if not txn:
        db.add(Transaction(
            id=data['transaction_id'],
            merchant_id=data['merchant_id'],
            amount=data['amount'],
            currency=data['currency'],
            status=data['event_type']
        ))
    else:
        if is_valid_transition(txn.status, data['event_type']):
            txn.status = data['event_type']


# ------------------ ROUTES ------------------

@app.route('/api/v1/events', methods=['POST'])
def ingest_event():
    """
    Ingest payment event
    ---
    tags:
      - Events
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - event_type
            - transaction_id
            - merchant_id
            - merchant_name
            - amount
            - currency
          properties:
            event_type: {type: string}
            transaction_id: {type: string}
            merchant_id: {type: string}
            merchant_name: {type: string}
            amount: {type: number}
            currency: {type: string}
            event_id: {type: string}
            timestamp: {type: string, format: date-time}
    responses:
      200:
        description: success or duplicate
      400:
        description: invalid input
      500:
        description: server error
    """
    data = request.json
    if not data:
        return error("request body required")

    msg = validate_event(data)
    if msg:
        return error(msg)

    db = get_db()

    upsert_merchant(db, data)

    
    event_data = {
        "transaction_id": data["transaction_id"],
        "merchant_id": data["merchant_id"],
        "event_type": data["event_type"],
        "amount": data["amount"],
        "currency": data["currency"]
    }
    
    if 'event_id' in data:
        event_data['event_id'] = data['event_id']
    
    if 'timestamp' in data and data['timestamp']:
        parsed_ts = parse_date(data['timestamp'])
        if parsed_ts:
            event_data['timestamp'] = parsed_ts

    event = Event(**event_data)

    try:
        db.add(event)
        db.flush()  
    except IntegrityError:
        db.rollback()

        existing = db.query(Event).filter_by(
            transaction_id=data["transaction_id"],
            event_type=data["event_type"]
        ).first()

        return success(
            data={"event_id": existing.event_id if existing else None},
            message="duplicate ignored"
        )

    
    upsert_transaction(db, data)

    
    db.commit()

    return success(
        data={
            "event_id": event.event_id,
            "transaction_id": data["transaction_id"],
            "event_type": data["event_type"]
        },
        message="event stored"
    )



@app.route('/api/v1/transactions', methods=['GET'])
def get_transactions():
    """
    Get transactions (cursor-based)
    ---
    tags:
      - Transactions
    parameters:
      - name: merchant_id
        in: query
        type: string
      - name: status
        in: query
        type: string
      - name: start_date
        in: query
        type: string
        format: date-time
      - name: end_date
        in: query
        type: string
        format: date-time
      - name: limit
        in: query
        type: integer
        default: 10
      - name: cursor
        in: query
        type: string
        description: "cursor format = cursor"
    responses:
      200:
        description: paginated transactions
    """
    db = get_db()

    try:
        query = db.query(Transaction)

        # -------- FILTERS --------
        merchant_id = request.args.get('merchant_id')
        status = request.args.get('status')
        start_date_raw = request.args.get('start_date')
        end_date_raw = request.args.get('end_date')

        if merchant_id:
            query = query.filter(Transaction.merchant_id == merchant_id)

        if status:
            query = query.filter(Transaction.status == status)

        start_date = parse_date(start_date_raw)
        end_date = parse_date(end_date_raw)

        if start_date_raw and not start_date:
            return error("invalid start_date format")

        if end_date_raw and not end_date:
            return error("invalid end_date format")

       
        if start_date:
            query = query.filter(
                Transaction.created_at != None,
                Transaction.created_at >= start_date
            )

        if end_date:
            query = query.filter(
                Transaction.created_at != None,
                Transaction.created_at <= end_date
            )

        # -------- CURSOR --------
        cursor = request.args.get('cursor')

        if cursor:
            c_dt, c_id = decode_cursor(cursor)

            if not c_dt:
                return error("invalid cursor")

            query = query.filter(
                Transaction.created_at != None,
                or_(
                    Transaction.created_at > c_dt,
                    and_(
                        Transaction.created_at == c_dt,
                        Transaction.id > c_id
                    )
                )
            )

        # -------- LIMIT --------
        try:
            limit = min(max(1, int(request.args.get('limit', 10))), 100)
        except:
            return error("invalid limit")

        # -------- FIXED ORDER (mandatory for cursor) --------
        query = query.filter(Transaction.created_at != None)\
             .order_by(Transaction.created_at, Transaction.id)

        # fetch one extra
        rows = query.limit(limit + 1).all()

        # If cursor was provided AND no new data → return empty
        if cursor and len(rows) == 0:
            return success({
                "transactions": [],
                "next_cursor": None
            })

        has_next = len(rows) > limit
        rows = rows[:limit]

        # -------- NEXT CURSOR --------
        next_cursor = None
        if has_next and rows:
            last = rows[-1]
            if last.created_at:
                next_cursor = encode_cursor(last.created_at, last.id)

        return success({
            "transactions": [
                {
                    "id": t.id,
                    "merchant_id": t.merchant_id,
                    "amount": t.amount,
                    "currency": t.currency,
                    "status": t.status,
                    "created_at": t.created_at.isoformat() if t.created_at else None
                }
                for t in rows
            ],
            "next_cursor": next_cursor
        })

    except Exception as e:
        return error(f"internal server error", 500)

    finally:
        db.close()


@app.route('/api/v1/transactions/<txn_id>', methods=['GET'])
def get_transaction(txn_id):
    """
    Get Transaction Details
    ---
    tags:
      - Transactions
    parameters:
      - name: txn_id
        in: path
        type: string
        required: true
        description: Transaction ID
    responses:
      200:
        description: Transaction details retrieved successfully
        schema:
          type: object
          properties:
            transaction:
              type: object
              properties:
                id:
                  type: string
                amount:
                  type: number
                currency:
                  type: string
                status:
                  type: string
                created_at:
                  type: string
                  format: date-time
            merchant:
              type: object
              nullable: true
              properties:
                id:
                  type: string
                name:
                  type: string
            events:
              type: array
              items:
                type: object
                properties:
                  event_id:
                    type: string
                  type:
                    type: string
                  amount:
                    type: number
                  currency:
                    type: string
                  timestamp:
                    type: string
                    format: date-time
      404:
        description: Transaction not found
      500:
        description: Internal server error
    """
    db = get_db()

    try:
        txn = db.query(Transaction).filter_by(id=txn_id).first()

        if not txn:
            return error("transaction not found", 404)

        # fetch merchant
        merchant = db.get(Merchant, txn.merchant_id)

        # fetch events (ordered timeline)
        events = db.query(Event)\
            .filter_by(transaction_id=txn_id)\
            .order_by(Event.timestamp)\
            .all()

        return success({
            "transaction": {
                "id": txn.id,
                "amount": txn.amount,
                "currency": txn.currency,
                "status": txn.status,
                "created_at": txn.created_at.isoformat() if txn.created_at else None
            },
            "merchant": {
                "id": merchant.id,
                "name": merchant.name
            } if merchant else None,
            "events": [
                {
                    "event_id": e.event_id,
                    "type": e.event_type,
                    "amount": e.amount,
                    "currency": e.currency,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None
                }
                for e in events
            ]
        })

    except Exception as e:
        return error(f"internal server error", 500)

    finally:
        db.close()


@app.route('/api/v1/reconciliation/summary', methods=['GET'])
def summary():
    """
    Reconciliation summary
    ---
    tags:
      - Reconciliation
    parameters:
      - name: group_by
        in: query
        type: string
        description: comma separated fields (merchant,date,status)
      - name: start_date
        in: query
        type: string
        format: date-time
      - name: end_date
        in: query
        type: string
        format: date-time
    responses:
      200:
        description: summary data
    """
    db = get_db()

    try:
        group_by = request.args.get('group_by', 'merchant,status')
        fields = set(group_by.split(','))

        query = db.query()

        select_fields = []
        group_fields = []

        # -------- DIMENSIONS --------
        if "merchant" in fields:
            select_fields.append(Transaction.merchant_id.label("merchant_id"))
            group_fields.append(Transaction.merchant_id)

        if "status" in fields:
            select_fields.append(Transaction.status.label("status"))
            group_fields.append(Transaction.status)

        if "date" in fields:
            date_col = func.date(Transaction.created_at)
            select_fields.append(date_col.label("date"))
            group_fields.append(date_col)

        # -------- AGGREGATION --------
        select_fields.append(func.count().label("count"))
        select_fields.append(func.sum(Transaction.amount).label("total_amount"))

        query = db.query(*select_fields)

        # -------- FILTERS --------
        start_date = parse_date(request.args.get('start_date'))
        end_date = parse_date(request.args.get('end_date'))

        if start_date:
            query = query.filter(Transaction.created_at >= start_date)

        if end_date:
            query = query.filter(Transaction.created_at <= end_date)

        # -------- GROUP BY --------
        if group_fields:
            query = query.group_by(*group_fields)

        results = query.all()

        return success([
            dict(r._mapping) for r in results
        ])

    except Exception as e:
        return error(f"internal server error", 500)

    finally:
        db.close()

@app.route('/api/v1/reconciliation/discrepancies', methods=['GET'])
def discrepancies():
    """
    Reconciliation discrepancies
    ---
    tags:
      - Reconciliation
    responses:
      200:
        description: discrepancy list
      500:
        description: server error
    """

    db = get_db()

    try:
        discrepancies = []

        # Processed but not settled
        processed_not_settled = db.query(Transaction).filter(
            Transaction.status == 'payment_processed',
            ~db.query(Event).filter(
                Event.transaction_id == Transaction.id,
                Event.event_type == 'settled'
            ).exists()
        ).all()

        for t in processed_not_settled:
            discrepancies.append({
                "id": t.id,
                "reason": "payment_processed but no settled event"
            })

        # Failed but settled
        failed_settled = db.query(Transaction).filter(
            Transaction.status == 'payment_failed',
            db.query(Event).filter(
                Event.transaction_id == Transaction.id,
                Event.event_type == 'settled'
            ).exists()
        ).all()

        for t in failed_settled:
            discrepancies.append({
                "id": t.id,
                "reason": "payment_failed but has settled event"
            })

        # Settled without processed (invalid transition)
        settled_no_processed = db.query(Transaction).filter(
            db.query(Event).filter(
                Event.transaction_id == Transaction.id,
                Event.event_type == 'settled'
            ).exists(),
            ~db.query(Event).filter(
                Event.transaction_id == Transaction.id,
                Event.event_type == 'payment_processed'
            ).exists()
        ).all()

        for t in settled_no_processed:
            discrepancies.append({
                "id": t.id,
                "reason": "settled event exists but no payment_processed event"
            })

        return success(discrepancies)

    except Exception:
        return error("internal server error", 500)

    finally:
        db.close()


if __name__ == "__main__":
    app.run(debug=True)