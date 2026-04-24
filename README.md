# PAY API

## Architecture Overview

This service ingests payment events and maintains transaction state.

Core components:

* Flask API (request handling)
* MySQL (data storage)
* SQLAlchemy (ORM)

Data model:

* Merchant → stores merchant info
* Transaction → current state of a payment
* Event → immutable event log

Flow:

1. Event is received via API
2. Merchant is upserted
3. Event is inserted (idempotent)
4. Transaction state is updated based on event

State transitions:

* payment_initiated → payment_processed → settled
* payment_processed → payment_failed

Invalid transitions are rejected.

---

## Setup (Local)

1. Install dependencies

```
pip install -r requirements.txt
```

2. Create `.env`

```
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=3306
DB_NAME=payment_db
```

3. Create database

```
python setup.py
```

4. Run server

```
python app.py
```

App runs at:

```
http://localhost:5000
```

---

## API Endpoints

### POST /api/v1/events

Ingest payment event

Request:

```
{
  "event_type": "payment_processed",
  "transaction_id": "txn_123",
  "merchant_id": "merchant_1",
  "merchant_name": "Amazon",
  "amount": 100,
  "currency": "USD"
}
```

Responses:

* 201 → event stored
* 200 → duplicate ignored
* 400 → invalid input

---

### GET /api/v1/transactions

List transactions (cursor-based)

Query params:

* merchant_id
* status
* start_date
* end_date
* limit
* cursor

---

### GET /api/v1/transactions/{id}

Get transaction details with events

---

### GET /api/v1/reconciliation/summary

Aggregated counts

Example:

```
?group_by=merchant,status,date
```

---

### GET /api/v1/reconciliation/discrepancies

Transactions processed but not settled

---

## Deployment

Run with:

```
gunicorn app:app --workers 4 --bind 0.0.0.0:8000
```

Environment variables required:

* DB_USER
* DB_PASSWORD
* DB_HOST
* DB_PORT
* DB_NAME

---

## Assumptions

* Events can be duplicated
* Idempotency handled using (transaction_id, event_type)
* Transaction state derived from events
* Events are processed in order (or validated)

---

## Tradeoffs

* Simple idempotency instead of full event_id deduplication
* Strong consistency using DB transactions
* Cursor pagination used instead of offset
* Single service (not split into microservices)
