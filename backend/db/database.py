import json

import asyncpg

from config import DB_HOSTS, DB_NAME, DB_USER, DB_PASS


pool = None


async def setup_connection(conn):
    await conn.set_type_codec(
        'jsonb', schema='pg_catalog', encoder=json.dumps, decoder=json.loads,
    )


async def connect_db():
    global pool
    pool = await asyncpg.create_pool(
        host=DB_HOSTS,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        target_session_attrs='read-write',
        min_size=1,
        max_size=5,
        timeout=5,
        command_timeout=10,
        init=setup_connection,
    )


async def close_db():
    if pool is not None:
        await pool.close()
