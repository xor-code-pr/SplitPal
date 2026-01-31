# SplitPal FastAPI Backend

Modern expense splitting application backend built with FastAPI and PostgreSQL.

## Quick Start

### 1. Setup

```bash
# Run setup script
setup.bat

# Or manually:
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 2. Configure

Edit `.env` file:
- Set `DATABASE_URL` to your PostgreSQL connection string
- Set `JWT_SECRET` to a secure random key
- Configure `ALLOWED_ORIGINS` for CORS

### 3. Run

```bash
# Windows
start.bat

# Or directly
uvicorn main:app --reload
```

### 4. Access

- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/ping

## Docker Deployment

```bash
# Using Docker Compose
docker-compose up -d

# Build manually
docker build -t splitpal-api .
docker run -p 8000:8000 splitpal-api
```

## Project Structure

```
splitpal-fastapi/
├── main.py              # FastAPI application entry point
├── app/
│   ├── __init__.py
│   ├── database.py      # PostgreSQL configuration
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic schemas
│   ├── dependencies.py  # Auth dependencies
│   ├── auth_utils.py    # JWT utilities
│   └── routers/         # API endpoints
│       ├── __init__.py
│       ├── auth.py
│       ├── groups.py
│       ├── transactions.py
│       ├── balances.py
│       ├── users.py
│       └── admin.py
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── start.bat            # Windows startup script
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/register` - Register user
- `POST /api/login` - Login user
- `POST /api/logout` - Logout user
- `POST /api/refresh` - Refresh token

### Groups
- `GET /api/groups` - List user groups
- `POST /api/groups` - Create group
- `POST /api/groups/{id}/members` - Add member
- `DELETE /api/groups/{id}/members/{user_id}` - Remove member

### Transactions
- `GET /api/groups/{id}/transactions` - List transactions
- `POST /api/transactions` - Create transaction
- `DELETE /api/transactions/{id}` - Delete transaction

### Balances
- `GET /api/groups/{id}/balances` - Get group balances

### Users
- `GET /api/users/lookup?email={email}` - Lookup user

### Admin
- `GET /api/admin/users` - List all users
- `DELETE /api/admin/users/{id}` - Delete user
- `GET /api/admin/groups` - List all groups
- `DELETE /api/admin/groups/{id}` - Delete group

## Technology Stack

- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Production database
- **SQLAlchemy 2.0** - Async ORM
- **Pydantic** - Data validation
- **JWT** - Authentication
- **Uvicorn** - ASGI server

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection URL | `postgresql+asyncpg://...` |
| JWT_SECRET | Secret key for JWT tokens | (required) |
| JWT_EXP_SECONDS | Access token expiry | 3600 (1 hour) |
| JWT_REFRESH_EXP_SECONDS | Refresh token expiry | 7776000 (90 days) |
| ALLOWED_ORIGINS | CORS allowed origins | `*` |

## Development

```bash
# Run with auto-reload
uvicorn main:app --reload

# Run on different port
uvicorn main:app --reload --port 8080

# Enable SQL logging
# Set DB_ECHO=true in .env
```

## Production Deployment

1. Set strong `JWT_SECRET`
2. Configure `ALLOWED_ORIGINS` appropriately
3. Use production PostgreSQL instance
4. Enable HTTPS
5. Use production ASGI server:

```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Security

- JWT token-based authentication
- Password hashing with bcrypt
- CORS protection
- SQL injection protection (SQLAlchemy)
- Input validation (Pydantic)

## License

[Your License]
