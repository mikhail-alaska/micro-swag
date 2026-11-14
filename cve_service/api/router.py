import httpx
from fastapi import APIRouter, HTTPException
from redis.exceptions import RedisError

from api.service import get_cve

router = APIRouter()


@router.get("/random")
async def hello_handler():
    try:
        return await get_cve()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail='Кэш CVE временно недоступен.') from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Источник CVE не ответил после нескольких попыток. Попробуйте позже.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        temporarily_unavailable = exc.response.status_code == 429 or exc.response.status_code >= 500
        headers = {}
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after:
            headers["Retry-After"] = retry_after

        raise HTTPException(
            status_code=503 if temporarily_unavailable else 502,
            detail=(
                "Источник CVE временно недоступен. Попробуйте позже."
                if temporarily_unavailable
                else f"Источник CVE вернул ошибку HTTP {exc.response.status_code}."
            ),
            headers=headers,
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="Не удалось подключиться к источнику CVE. Попробуйте позже.",
        ) from exc
