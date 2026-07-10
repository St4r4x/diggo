from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

import api
from db import open_db
from env import load_env

load_env()

_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://career:career@localhost:5432/career"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = open_db(_DATABASE_URL)
    yield
    app.state.db.close()


app = FastAPI(lifespan=lifespan)

app.include_router(api.router)
