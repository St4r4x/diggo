from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import api
from db import open_db
from env import load_env

load_env()

_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://career:career@localhost:5432/career"
)
_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = open_db(_DATABASE_URL)
    yield
    app.state.db.close()


app = FastAPI(lifespan=lifespan)

if _ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api.router)
