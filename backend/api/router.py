import secrets
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Depends, Header, Query, Request

import db.database as database
import queue_client
from api.schemas import BrowserInfo
from api.service import back_to_cve, register_click
from config import ADMIN_TOKEN, PROXY_TOKEN
from db.models import get_history, get_visitors, update_visitor, delete_click

router = APIRouter()


async def check_admin(x_admin_token: str | None = Header(default=None)):
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail='Нужен X-Admin-Token.')


@router.get("/hello")
async def hello_handler():
    return "hello world"


@router.get('/health')
async def health():
    async with database.pool.acquire() as conn:
        await conn.fetchval('SELECT 1')
    if queue_client.connection is None or not queue_client.connection.connected.is_set():
        raise HTTPException(status_code=503, detail='Очередь переподключается.')
    return {'status': 'ok'}


@router.post('/click')
async def click(browser: BrowserInfo, request: Request):
    ip = request.client.host if request.client else 'unknown'
    if PROXY_TOKEN and secrets.compare_digest(request.headers.get('x-proxy-token', ''), PROXY_TOKEN):
        ip = request.headers.get('x-real-ip', ip)
    try:
        result = await register_click(
            browser,
            ip,
            request.headers.get('user-agent', ''),
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail='Не удалось получить CVE.') from exc
    if result is None:
        raise HTTPException(status_code=503, detail='Список CVE пока пуст.')
    return result


@router.get('/history', dependencies=[Depends(check_admin)])
async def history(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    return await get_history(limit, offset)


@router.get('/visitors', dependencies=[Depends(check_admin)])
async def visitors():
    return await get_visitors()


@router.patch('/visitors/{visitor_id}', dependencies=[Depends(check_admin)])
async def visitor_update(visitor_id: int, browser: BrowserInfo):
    result = await update_visitor(visitor_id, browser)
    if result is None:
        raise HTTPException(status_code=404, detail='Посетитель не найден.')
    return result


@router.delete('/history/{event_id}', dependencies=[Depends(check_admin)])
async def history_delete(event_id: UUID):
    if not await delete_click(event_id):
        raise HTTPException(status_code=404, detail='Нажатие не найдено.')
    return {'deleted': True}


@router.get("/")
async def all_handler():
    try:
        return await back_to_cve()
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Сервис CVE не ответил вовремя. Попробуйте позже.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code not in {502, 503, 504}:
            status_code = 502

        detail = "Сервис CVE недоступен. Попробуйте позже."
        try:
            data = exc.response.json()
            if isinstance(data, dict) and isinstance(data.get("detail"), str):
                detail = data["detail"]
        except ValueError:
            pass

        headers = {}
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after:
            headers["Retry-After"] = retry_after

        raise HTTPException(
            status_code=status_code,
            detail=detail,
            headers=headers,
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="Не удалось подключиться к сервису CVE. Попробуйте позже.",
        ) from exc
