# Phone Number Refresh System

A small Flask web app that refreshes phone numbers against multiple telecom providers (Layan, Aloha, Areen) by looking up the associated company in a PostgreSQL database (shared with the `recharge-desk` Django project).

## Project structure

```
refresh_numbers/
├── app.py                 # Flask app + /refresh endpoint
├── rn.py                  # Provider handlers (layan / aloha / areen)
├── requirements.txt
├── .env                   # DB credentials (NOT committed)
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── script.js
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
PG_HOST=127.0.0.1
PG_PORT=5432
PG_DB=recharge_desk
PG_USER=recharge_readonly
PG_PASSWORD=your_password_here
```

## Run

```bash
python app.py
```

Open http://localhost:5000

## API

`POST /refresh`

Request:

```json
{ "phone_number": "05XXXXXXXX" }
```

Response:

```json
{ "code": 1, "message": "Number refreshed successfully" }
```

### Response codes

| Code | Meaning |
|------|---------|
| 0    | Number not found |
| 1    | Successful refresh |
| 2    | Wait (rate-limited by provider) |
| 4    | Unknown / error |

## Database

Reads from the `recharge-desk` PostgreSQL database using a **read-only** user. Query joins `sales_sale` with `companies_company` using `reference_number` (phone number) to determine the company and dispatch to the matching provider handler.
