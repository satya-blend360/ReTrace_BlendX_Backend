 

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router
from src.snowflake.router import router as snowflake_router
from src.aws.router import router as aws_router

app = FastAPI(title="Smart Recruiter Backend")

# CORS (Frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middlewares

# Routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(snowflake_router, prefix="/events", tags=["Snowflake"])
app.include_router(aws_router, prefix="/cortex", tags=["Cortex Services"])

# Root Health Check
@app.get("/", tags=["Health"])
def root():
    return {"status": "OK", "service": "Smart Recruiter Backend is running!"}
