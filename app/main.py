"""
main.py — FastAPI application entry point.

Registers all routers and configures CORS so the Next.js frontend (localhost:3000)
can make requests to this API (localhost:8000).

Run with:
  uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import bookings, inquiries, admin, slots, whatsapp

# ─── App Init ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Parabolica API",
    description="Backend for the Parabolica VR Entertainment booking and admin system.",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc",     # ReDoc at http://localhost:8000/redoc
)

# ─── CORS Middleware ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register Routers ─────────────────────────────────────────────────────────
app.include_router(bookings.router)
app.include_router(inquiries.router)
app.include_router(admin.router)
app.include_router(slots.router)
app.include_router(whatsapp.router)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ONLINE", "system": "Parabolica Mission Control API v1.0"}

@app.get("/health", tags=["Health"])
def health():
    return {"status": "OK"}
