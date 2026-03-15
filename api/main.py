"""FastAPI application entry point."""

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import dashboard, pipeline, applications, config, drafts
from api.state import pipeline_state

app = FastAPI(title="YC Applier API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api/pipeline")
app.include_router(applications.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(drafts.router, prefix="/api/drafts")


@app.on_event("startup")
async def startup():
    pipeline_state.set_loop(asyncio.get_event_loop())


# Serve React frontend build in production
_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="static")
