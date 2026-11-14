import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx
import redis.asyncio as redis

r = redis.Redis(
    host='redis', port=6379, decode_responses=True,
    socket_connect_timeout=3, socket_timeout=5,
)

CVE_POOL_KEY = "cve:pool:360d:v1"
CVE_POOL_TTL = 3600
NVD_MAX_ATTEMPTS = 4
NVD_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
NVD_MAX_RETRY_DELAY = 60.0
cache_fill_lock = asyncio.Lock()
logger = logging.getLogger(__name__)


def extract_cvss_score(metrics):
    metrics = metrics or {}

    versions = (
        "cvssMetricV40",
        "cvssMetricV31",
        "cvssMetricV30",
        "cvssMetricV2",
    )

    for version in versions:
        entries = metrics.get(version) or []

        entries = sorted(
            entries,
            key=lambda entry: entry.get("type") != "Primary",
        )

        for entry in entries:
            cvss_data = entry.get("cvssData") or {}
            score = cvss_data.get("baseScore")

            if score is not None:
                return score

    return None


async def get_cve():
    a = await redis_cve()
    return a


def nvd_retry_delay(attempt, response=None):
    delay = min(6.5 * 2 ** attempt, NVD_MAX_RETRY_DELAY)

    if response is not None:
        retry_after = response.headers.get("Retry-After")

        if retry_after:
            try:
                seconds = int(retry_after)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    seconds = 0

            # Не повторяем раньше указанного срока и не ждём без ограничения.
            if seconds > NVD_MAX_RETRY_DELAY:
                return None

            delay = max(delay, seconds)

    return delay


async def request_nvd_page(client, params):
    for attempt in range(NVD_MAX_ATTEMPTS):
        try:
            response = await client.get(
                "https://services.nvd.nist.gov/rest/json/cves/2.0",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            response = exc.response if isinstance(exc, httpx.HTTPStatusError) else None

            if response is not None and response.status_code not in NVD_RETRYABLE_STATUSES:
                raise

            if attempt == NVD_MAX_ATTEMPTS - 1:
                raise

            delay = nvd_retry_delay(attempt, response)
            if delay is None:
                raise

            reason = f"HTTP {response.status_code}" if response is not None else type(exc).__name__
            logger.warning(
                "NVD: %s, попытка %s/%s; повтор страницы startIndex=%s через %.1f с",
                reason,
                attempt + 1,
                NVD_MAX_ATTEMPTS,
                params.get("startIndex"),
                delay,
            )
            await asyncio.sleep(delay)


async def iter_cves_last_360_days():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    seen_ids = set()
    first_request = True

    async with httpx.AsyncClient(timeout=30.0) as client:
        for offset in range(0, 360, 120):
            end = now - timedelta(days=offset)
            start = now - timedelta(days=offset + 120)
            start_index = 0

            while True:
                if not first_request:
                    await asyncio.sleep(6.5)
                first_request = False

                data = await request_nvd_page(
                    client,
                    {
                        "pubStartDate": start.isoformat(timespec="seconds"),
                        "pubEndDate": end.isoformat(timespec="seconds"),
                        "resultsPerPage": 2000,
                        "startIndex": start_index,
                    },
                )
                vulns = data.get("vulnerabilities") or []

                if not vulns:
                    break

                for vuln in vulns:
                    cve = vuln.get("cve") or {}
                    cve_id = cve.get("id")

                    if cve_id and cve_id not in seen_ids:
                        seen_ids.add(cve_id)
                        yield cve

                start_index += len(vulns)

                if start_index >= data.get("totalResults", 0):
                    break


async def redis_cve():
    cached = await r.get(CVE_POOL_KEY)

    if cached:
        pool = json.loads(cached)
        if isinstance(pool, list) and pool:
            return random.choice(pool)

    async with cache_fill_lock:
        # Другой запрос мог заполнить кэш, пока мы ожидали блокировку.
        cached = await r.get(CVE_POOL_KEY)

        if cached:
            pool = json.loads(cached)
            if isinstance(pool, list) and pool:
                return random.choice(pool)

        pool = []

        async for cve in iter_cves_last_360_days():
            descriptions = cve.get("descriptions") or []
            description = None

            for elem in descriptions:
                if elem.get("lang") == "en" and elem.get("value"):
                    description = elem.get("value")
                    break

            if not description and descriptions:
                description = descriptions[0].get("value")

            out = {
                "id": cve.get("id"),
                "description": description,
                "cvss_score": extract_cvss_score(cve.get("metrics"))
            }
            pool.append(out)

        if not pool:
            return None

        await r.set(CVE_POOL_KEY, json.dumps(pool), ex=CVE_POOL_TTL)
        return random.choice(pool)
