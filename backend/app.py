from contextlib import asynccontextmanager

import aio_pika
import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.router import router as api_router
from db.database import connect_db, close_db
from queue_client import connect_queue, close_queue


@asynccontextmanager
async def lifespan(app):
    try:
        await connect_db()
        await connect_queue()
        yield
    finally:
        await close_queue()
        await close_db()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(asyncpg.PostgresError)
async def database_error(request: Request, exc):
    return JSONResponse(status_code=503, content={'detail': 'БД временно недоступна.'})


@app.exception_handler(aio_pika.exceptions.AMQPException)
async def queue_error(request: Request, exc):
    return JSONResponse(status_code=503, content={'detail': 'Очередь временно недоступна.'})


@app.exception_handler(TimeoutError)
async def timeout_error(request: Request, exc):
    return JSONResponse(status_code=503, content={'detail': 'Сервис не ответил вовремя.'})


@app.exception_handler(OSError)
async def connection_error(request: Request, exc):
    return JSONResponse(status_code=503, content={'detail': 'Не удалось подключиться к сервису.'})

app.include_router(router=api_router)
