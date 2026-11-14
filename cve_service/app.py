from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.router import router as api_router
from api.service import r


@asynccontextmanager
async def lifespan(app):
    try:
        yield
    finally:
        await r.aclose()


app = FastAPI(lifespan=lifespan)

app.include_router(router=api_router)
