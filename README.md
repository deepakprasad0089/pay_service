# Payment Service API

A lightweight backend service for payment event ingestion, transaction reconciliation, and state management. Built with Flask, MySQL, and SQLAlchemy.

---

## Architecture Overview

### Tech Stack
- **Framework**: Flask 3.0.3
- **Database**: MySQL with PyMySQL
- **ORM**: SQLAlchemy 2.0
- **API Documentation**: Flasgger (Swagger UI)
- **Server**: Gunicorn (production)

### Core Components

* Flask API (request handling)
* MySQL (data storage)
* SQLAlchemy ORM (database abstraction)

### Data Model

* **Merchant** → stores merchant info
* **Transaction** → current state of a payment
* **Event** → immutable event log with unique constraint on (transaction_id, event_type)

### Processing Flow

1. Event is received via POST /api/v1/events
2. Merchant is created/upserted  
3. Transaction is created/upserted, then FLUSHED to DB
4. Event is inserted (caught as duplicate if (txn_id, type) exists)
5. Transaction status is updated based on event type (if valid transition)
6. All changes are COMMITTED

### State Transitions

Valid paths:
* payment_initiated → payment_processed → settled
* payment_initiated → payment_processed → payment_failed
* Invalid transitions are silently rejected

---

## Setup (Local)

### Prerequisites
- Python 3.9+
- MySQL 5.7+
- pip / virtualenv

### Steps

1. **Install dependencies**

```bash
pip install -r requirements.txt
```

2. **Create `.env`**

```
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=3306
DB_NAME=payment_db
```

3. **Create database**

```bash
python setup.py
```

4. **Seed sample data (optional)**

```bash
python seed.py
```

This loads ~10,000 events from `sample_events.json` with realistic scenarios.

5. **Run server**

```bash
python app.py
```

Server: `http://localhost:5000`

Swagger UI: `http://localhost:5000/apidocs`

---

## Project Structure

```
pay_service/
├── app.py              # Flask app with all endpoints
├── models.py           # SQLAlchemy models
├── db.py              # Database connection
├── utils.py           # Helper functions
├── seed.py            # Load sample data
├── setup.py           # Initialize schema
├── Dockerfile         # Container config
├── requirements.txt   # Dependencies
├── sample_events.json # ~10,000 events
└── README.md
```

## API Endpoints

### 1. POST /api/v1/events

Ingest payment events and maintain transaction state.

**Request:**
```json
{
  "event_id": "evt_abc123",
  "event_type": "payment_initiated",
  "transaction_id": "txn_123",
  "merchant_id": "merchant_1",
  "merchant_name": "Amazon",
  "amount": 1500.50,
  "currency": "USD",
  "timestamp": "2026-04-26T10:00:00Z"
}
```

**Event Types:** payment_initiated, payment_processed, payment_failed, settled

**Response (Success - 200):**
```json
{"data": {"event_id": "...", "transaction_id": "...", "event_type": "..."}, "message": "event stored"}
```

---

### 2. GET /api/v1/transactions

List transactions with cursor-based pagination.

**Query Params:** merchant_id, status, start_date, end_date, limit (1-100), cursor

**Example:** `GET /api/v1/transactions?merchant_id=merchant_1&limit=20`

---

### 3. GET /api/v1/transactions/{transaction_id}

Get transaction details with full event history.

**Response:** transaction object, merchant info, and all events in chronological order

---

### 4. GET /api/v1/reconciliation/summary

Aggregated transaction metrics.

**Query Params:** group_by (merchant, status, date), start_date, end_date

**Example:** `GET /api/v1/reconciliation/summary?group_by=merchant,status`

---

### 5. GET /api/v1/reconciliation/discrepancies

Find transactions with state inconsistencies: processed but not settled, failed but settled, etc.

---

## Deployment

### Running with Gunicorn (Recommended)

```bash
gunicorn app:app --workers 4 --bind 0.0.0.0:8000 --timeout 30
```

### Docker

```bash
docker build -t pay-service .
docker run -p 8080:8080 \
  -e DB_USER=root \
  -e DB_PASSWORD=secret \
  -e DB_HOST=db.example.com \
  -e DB_PORT=3306 \
  -e DB_NAME=payment_db \
  pay-service
```

### Environment Variables Required

* DB_USER
* DB_PASSWORD
* DB_HOST
* DB_PORT
* DB_NAME

---

## Assumptions

* Events can be duplicated
* Idempotency handled using (transaction_id, event_type) unique constraint
* Transaction state derived from events
* Timestamps handled in UTC

---

## Key Design Decisions

### 1. Idempotency
- Unique constraint on (transaction_id, event_type)
- Prevents duplicate events for same transaction/type combo
- IntegrityError caught and existing event returned

### 2. Event ID Generation
- Generated in Python using uuid.uuid4()
- Ensures event_id available immediately in response
- Not reliant on database defaults

### 3. Transaction Flush Before Event Insert
- Transaction must exist before Event (foreign key requirement)
- db.flush() called after upsert_transaction()
- Then Event safely references transaction

### 4. Cursor-Based Pagination
- Composite index on (created_at, id)
- Efficient for large datasets
- Cursor encoded as base64 JSON

### 5. State Transitions
- Strict state machine: initiated → processed → settled
- Silent rejection of invalid transitions
- Transaction state unchanged if invalid

### 6. Time Zone Handling
- All timestamps in UTC
- Returned as ISO 8601 with timezone
- Consistency across regions

---

## Deployment

Run with Gunicorn:
```bash
gunicorn app:app --workers 4 --bind 0.0.0.0:8000
```

Environment variables required:
* DB_USER
* DB_PASSWORD
* DB_HOST
* DB_PORT
* DB_NAME

Docker:
```bash
docker build -t pay-service .
docker run -p 8080:8080 -e DB_USER=root ... pay-service
```

---

