import db.database as database


async def save_click(event):
    async with database.pool.acquire() as conn:
        async with conn.transaction():
            visitor_id = await conn.fetchval('''
                INSERT INTO visitors
                    (fingerprint, ip, user_agent, browser, first_seen, last_seen)
                VALUES ($1, $2, $3, $4, $5, $5)
                ON CONFLICT (fingerprint) DO UPDATE SET
                    ip = EXCLUDED.ip,
                    user_agent = EXCLUDED.user_agent,
                    browser = EXCLUDED.browser,
                    last_seen = GREATEST(visitors.last_seen, EXCLUDED.last_seen)
                RETURNING id
            ''', event.fingerprint, event.ip, event.user_agent,
                event.browser.model_dump(exclude_none=True), event.created_at)

            await conn.execute('''
                INSERT INTO clicks
                    (event_id, visitor_id, cve_id, description, cvss_score, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (event_id) DO NOTHING
            ''', event.event_id, visitor_id, event.cve.id,
                event.cve.description, event.cve.cvss_score, event.created_at)


async def get_history(limit, offset):
    async with database.pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT c.event_id, c.visitor_id, c.cve_id, c.description,
                   c.cvss_score, c.created_at, v.fingerprint,
                   v.ip, v.user_agent, v.browser
            FROM clicks c
            JOIN visitors v ON v.id = c.visitor_id
            ORDER BY c.created_at DESC, c.event_id
            LIMIT $1 OFFSET $2
        ''', limit, offset)
    return [dict(row) for row in rows]


async def get_visitors():
    async with database.pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT id, fingerprint, ip, user_agent, browser, first_seen, last_seen
            FROM visitors ORDER BY last_seen DESC LIMIT 100
        ''')
    return [dict(row) for row in rows]


async def update_visitor(visitor_id, browser):
    async with database.pool.acquire() as conn:
        row = await conn.fetchrow('''
            UPDATE visitors SET browser = $2
            WHERE id = $1
            RETURNING id, fingerprint, browser, first_seen, last_seen
        ''', visitor_id, browser.model_dump(exclude_none=True))
    return dict(row) if row else None


async def delete_click(event_id):
    async with database.pool.acquire() as conn:
        deleted = await conn.fetchval(
            'DELETE FROM clicks WHERE event_id = $1 RETURNING event_id', event_id,
        )
    return deleted is not None
