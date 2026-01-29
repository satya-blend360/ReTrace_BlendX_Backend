# 🚀 Quick Start Guide

Get your BlendX Backend API running in 5 minutes!

## Step 1: Install Python (if needed)

Download and install Python 3.9 or higher from [python.org](https://www.python.org/downloads/)

Verify installation:
```bash
python --version
```

## Step 2: Set Up Project

```bash
# Navigate to project directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 3: Configure Environment

```bash
# Copy environment template
cp example.env .env

# Edit .env file with your text editor
# Fill in at minimum:
# - Azure AD credentials (SSO_CLIENT_ID, SSO_CLIENT_SECRET, SSO_TENANT_ID)
# - JWT_SECRET (generate a random string)
# - Snowflake credentials (SF_ACCOUNT, SF_USER, SF_PASSWORD, etc.)
```

**Generate a secure JWT secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Step 4: Run the Server

```bash
uvicorn src.main:app --reload
```

✅ API is now running at: http://localhost:8000

## Step 5: Test the API

Open your browser and visit:
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/

## Next Steps

- Review [README.md](README.md) for detailed documentation
- Configure Azure AD app registration
- Set up Snowflake database and tables
- Deploy with Docker (optional)

## Common Commands

```bash
# Start development server
uvicorn src.main:app --reload

# Start with custom port
uvicorn src.main:app --reload --port 8001

# Run tests
pytest

# Install new package
pip install package-name
pip freeze > requirements.txt

# Deactivate virtual environment
deactivate
```

## Need Help?

Check the [Troubleshooting section](README.md#-troubleshooting) in README.md

---
Happy coding! 🎉
