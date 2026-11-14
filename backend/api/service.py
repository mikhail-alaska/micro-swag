import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from api.schemas import ClickEvent, CveInfo
from queue_client import publish_click


async def back_to_cve():
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=600.0)) as client:
        a = await client.get('http://cve_service:8000/random')

    a.raise_for_status()
    return a.json()


async def register_click(browser, ip, user_agent):
    cve = await back_to_cve()
    if not isinstance(cve, dict) or not cve.get('id'):
        return None

    browser_data = browser.model_dump(exclude_none=True)
    fingerprint_data = json.dumps(
        {'user_agent': user_agent, 'browser': browser_data},
        sort_keys=True,
        separators=(',', ':'),
    )
    fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()

    event = ClickEvent(
        event_id=uuid4(),
        fingerprint=fingerprint,
        ip=ip,
        user_agent=user_agent,
        browser=browser,
        cve=CveInfo.model_validate(cve),
        created_at=datetime.now(timezone.utc),
    )
    await publish_click(event)

    return {
        'message': 'hello world',
        'event_id': event.event_id,
        'fingerprint': fingerprint,
        'cve': event.cve.model_dump(),
    }
