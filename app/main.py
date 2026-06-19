"""
HackBridge — FastAPI Application Entry Point
AI-Enabled Hackathon Management Platform

Architecture:
  main.py          → App factory, CORS, router mounting
  database.py      → Supabase client singleton
  models.py        → Pydantic request/response schemas
  routers/auth.py  → GoTrue auth wrapper
  routers/dashboard.py → Organizer metrics & leaderboard
  routers/ai.py    → AI endpoints (skills, dedupe, assignment, bias)
  services/        → Business logic for each AI feature
"""

import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load environment variables before any module imports that depend on them
load_dotenv()

from app.routers import auth, dashboard, ai  # noqa: E402


# ── Lifespan: pre-warm the sentence-transformers model on startup ────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Pre-loads the sentence-transformer model into memory at startup
    so the first /assign-reviewers call doesn't incur a cold-start penalty.
    """
    print("⚡ HackBridge API starting up...")
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("✅ Sentence-transformer model loaded (all-MiniLM-L6-v2)")
    except Exception as e:
        print(f"⚠️  Model pre-load skipped: {e}")

    yield  # Application runs here

    print("🛑 HackBridge API shutting down.")


# ── App Factory ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="HackBridge API",
    description=(
        "AI-enabled hackathon management platform with intelligent "
        "deduplication, skill extraction, reviewer assignment, and bias detection."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS — allow all origins for hackathon demo flexibility ──────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request timing middleware (useful for performance benchmarking) ───────────

@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    return response


# ── Mount Routers ────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(ai.router)


# ── Root & Health ────────────────────────────────────────────────────────────

from fastapi.responses import FileResponse

@app.get("/", tags=["UI"])
async def root():
    return FileResponse("HackBridge_complete.html")


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Lightweight health probe for monitoring & load balancers.
    Verifies Supabase connectivity.
    """
    from app.database import get_supabase

    try:
        sb = get_supabase()
        # Quick connectivity test — fetch 1 row from hackathons
        sb.table("hackathons").select("id").limit(1).execute()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
    }


# ── Global Exception Handler ────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url),
        },
    )


# ── Direct execution ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
