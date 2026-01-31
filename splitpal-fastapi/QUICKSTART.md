# 🚀 Quick Start Guide

## Step 1: Navigate to the FastAPI folder

```bash
cd c:\MyFiles\MyProjects\MyHelpers\Splitpal\splitpal-backend\splitpal-fastapi
```

## Step 2: Run setup

```bash
setup.bat
```

This will:
- Create a virtual environment
- Create .env from template

## Step 3: Edit .env file

Open `.env` and configure:

```env
# Required: Set your PostgreSQL connection
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/splitpal

# Required: Generate a secure secret
JWT_SECRET=<run: python -c "import secrets; print(secrets.token_urlsafe(32))">

# Optional: Configure CORS for your frontend
ALLOWED_ORIGINS=http://localhost:3000
```

## Step 4: Install dependencies

```bash
venv\Scripts\activate
pip install -r requirements.txt
```

## Step 5: Ensure PostgreSQL is running

Make sure you have PostgreSQL installed and running, then create the database:

```sql
CREATE DATABASE splitpal;
```

## Step 6: Start the server

```bash
start.bat
```

Or manually:
```bash
uvicorn main:app --reload
```

## Step 7: Verify it's working

Open your browser:

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/ping

## 🎉 You're Ready!

The API is now running at http://localhost:8000

### Test it out:

1. Go to http://localhost:8000/docs
2. Try the `/api/ping` endpoint
3. Register a new user with `/api/register`
4. Login with `/api/login`
5. Use the returned token for authenticated endpoints

## 🐳 Alternative: Docker

If you prefer Docker:

```bash
docker-compose up -d
```

This automatically:
- Sets up PostgreSQL
- Configures the database
- Starts the API
- No manual configuration needed!

Access at http://localhost:8000

## 📚 Next Steps

- Read [README.md](README.md) for full documentation
- Check [MIGRATION_COMPLETE.md](MIGRATION_COMPLETE.md) for structure details
- Explore the API at http://localhost:8000/docs

## 🆘 Troubleshooting

### Can't connect to database?
- Verify PostgreSQL is running
- Check DATABASE_URL in .env
- Ensure database exists: `CREATE DATABASE splitpal;`

### Import errors?
- Activate virtual environment: `venv\Scripts\activate`
- Install dependencies: `pip install -r requirements.txt`

### Port 8000 already in use?
- Change port in start.bat or run: `uvicorn main:app --reload --port 8080`

---

**Happy coding! 🎉**
