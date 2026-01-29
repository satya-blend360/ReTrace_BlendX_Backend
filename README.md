# BlendX Backend - Smart Recruiter API

A FastAPI-based backend service for smart recruiting with Azure AD authentication, Snowflake data warehouse integration, and AWS services for resume processing.

## 🚀 Features

- **Authentication & Authorization**: Microsoft Azure AD SSO integration with JWT tokens
- **Snowflake Integration**: Event tracking, dashboard analytics, and AI-powered insights
- **AWS Services**: Resume parsing and candidate extraction with embedding capabilities
- **Analytics Dashboard**: Real-time metrics, forecast accuracy, supplier performance
- **AI-Powered Analysis**: Cortex AI for stockout analysis and root cause detection
- **Docker Support**: Containerized deployment ready

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.9+** (Python 3.9 recommended)
- **pip** (Python package manager)
- **Git** (for version control)
- **Docker** (optional, for containerized deployment)

## 🛠️ Installation & Setup

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd backend
```

### 2. Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the root directory by copying the example:

```bash
cp example.env .env
```

Then edit `.env` with your actual credentials (see Configuration section below).

### 5. Run the Application

**Development Mode:**
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Production Mode:**
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at: `http://localhost:8000`

## 🔧 Configuration

### Required Environment Variables

Edit your `.env` file with the following configurations:

#### Azure AD Authentication (SSO)
- `SSO_CLIENT_ID`: Your Azure AD application client ID
- `SSO_CLIENT_SECRET`: Azure AD application client secret
- `SSO_TENANT_ID`: Azure AD tenant ID

#### Azure AD Graph API (for user management)
- `AD_CLIENT_ID`: Azure AD client ID for Graph API
- `AD_CLIENT_SECRET`: Azure AD client secret
- `AD_TENANT_ID`: Azure AD tenant ID
- `APP_USERS_GROUP_ID`: Azure AD group ID for app users

#### JWT Configuration
- `JWT_SECRET`: Secret key for JWT token signing (use a strong random string)
- `JWT_EXPECTED_AUDIENCE`: Expected audience for JWT validation
- `REDIRECT_URI`: OAuth redirect URI for your application

#### Snowflake Configuration
- `SF_ACCOUNT`: Snowflake account identifier
- `SF_USER`: Snowflake username
- `SF_PASSWORD`: Snowflake password
- `SF_DATABASE`: Snowflake database name
- `SF_SCHEMA`: Snowflake schema name
- `SF_WAREHOUSE`: Snowflake warehouse name
- `SF_ROLE`: Snowflake role name

#### Application Settings
- `ENVIRONMENT`: Environment name (development/staging/production)
- `IT_COMMS_MAIL`: IT communications email address

See `example.env` for a complete template with all required variables.

## 🐳 Docker Deployment

### Build Docker Image

```bash
docker build -t blendx-backend .
```

### Run Docker Container

```bash
docker run -d -p 8000:8000 --env-file .env --name blendx-api blendx-backend
```

### Docker Compose (Optional)

Create a `docker-compose.yml` file:

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
```

Run with:
```bash
docker-compose up -d
```

## 📚 API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🗂️ Project Structure

```
backend/
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── auth/                   # Authentication & authorization
│   │   ├── router.py          # Auth endpoints
│   │   ├── models.py          # Auth data models
│   │   └── dependencies.py    # JWT utilities
│   ├── snowflake/             # Snowflake integration
│   │   ├── router.py          # Event & analytics endpoints
│   │   ├── service.py         # Business logic
│   │   └── models.py          # Data models
│   ├── aws/                   # AWS services
│   │   ├── router.py          # Resume processing endpoints
│   │   ├── service.py         # AWS integration logic
│   │   └── models.py          # Data models
│   └── utils/                 # Utilities
│       ├── config.py          # Configuration management
│       ├── database.py        # Database connections
│       └── extract_candidates.py  # Resume parsing
├── requirements.txt           # Python dependencies
├── Dockerfile                # Docker configuration
├── example.env               # Environment template
├── .env                      # Your local configuration (create this)
└── README.md                 # This file
```

## 🔑 API Endpoints

### Authentication (`/auth`)
- `POST /auth/token` - Authenticate with Azure AD and get JWT token

### Events (`/events`)
- `GET /events` - Get events list
- `GET /events/details` - Get event details
- `GET /events/dashboard-summary` - Dashboard metrics
- `GET /events/root-cause-distribution` - Root cause analysis
- `GET /events/inventory-timeline` - Inventory trends
- `GET /events/forecast-accuracy` - Forecast metrics
- `GET /events/supplier-performance` - Supplier analytics
- `POST /events/analyze-stockout` - AI-powered stockout analysis

### Cortex Services (`/cortex`)
- `GET /cortex/health` - Service health check
- `POST /cortex/upload` - Upload and process resumes
- `POST /cortex/embed` - Generate embeddings

### Health
- `GET /` - Root health check

## 🧪 Testing

Run the test suite:

```bash
pytest
```

Run specific test file:
```bash
python test.py
```

## 🔒 Security Notes

1. **Never commit `.env` file** to version control
2. Use strong, unique values for `JWT_SECRET`
3. Restrict CORS origins in production (update `main.py`)
4. Use HTTPS in production environments
5. Rotate credentials regularly
6. Keep dependencies updated: `pip install --upgrade -r requirements.txt`

## 🐛 Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'xyz'`
- **Solution**: Ensure virtual environment is activated and run `pip install -r requirements.txt`

**Issue**: `Connection refused` to Snowflake
- **Solution**: Check Snowflake credentials in `.env` and network connectivity

**Issue**: Azure AD authentication fails
- **Solution**: Verify Azure AD app registration and redirect URI configuration

**Issue**: Port 8000 already in use
- **Solution**: Use a different port: `uvicorn src.main:app --port 8001`

### Enable Debug Logging

Set log level in your run command:
```bash
uvicorn src.main:app --reload --log-level debug
```

## 📝 Sample Data

The project includes sample CSV files for testing:
- `demand_forecast.csv` - Demand forecasting data
- `inventory_snapshot.csv` - Inventory levels
- `purchase_orders.csv` - Purchase order history
- `reorder_rules.csv` - Reorder point rules
- `stockout_events.csv` - Stockout event logs

Use `SampleData.py` to load sample data into your Snowflake database.

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -am 'Add new feature'`
3. Push to branch: `git push origin feature/your-feature`
4. Submit a pull request

## 📄 License

[Your License Here]

## 👥 Support

For support, email [your-email] or create an issue in the repository.

---

**Built with ❤️ using FastAPI, Snowflake, and Azure**
