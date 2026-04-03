from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import auth, campaigns, tracking, dashboard, ai_generator, custom_filters, reports, public_pages

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(campaigns.router, prefix=settings.API_PREFIX)
app.include_router(tracking.router, prefix=settings.API_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_PREFIX)
app.include_router(ai_generator.router, prefix=settings.API_PREFIX)
app.include_router(custom_filters.router, prefix=settings.API_PREFIX)
app.include_router(reports.router, prefix=settings.API_PREFIX)
app.include_router(public_pages.router, prefix=settings.API_PREFIX)

@app.get("/")
def root():
    return {"message": "Traffic Guardian API", "version": settings.VERSION}

@app.get("/api")
def api_root():
    return {"message": "Traffic Guardian API", "version": settings.VERSION}

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "cors_origins": settings.CORS_ORIGINS,
        "api_prefix": settings.API_PREFIX
    }
