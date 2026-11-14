import asyncio
import logging

import aio_pika
import asyncpg
from pydantic import ValidationError

import queue_client
from api.schemas import ClickEvent
from db.database import connect_db, close_db
from db.models import save_click


logger = logging.getLogger(__name__)


async def main():
    await connect_db()
    await queue_client.connect_queue()

    try:
        async with queue_client.queue.iterator() as messages:
            async for message in messages:
                try:
                    event = ClickEvent.model_validate_json(message.body)
                except ValidationError:
                    await message.reject(requeue=False)
                    logger.exception('Неправильное событие в очереди')
                    continue

                try:
                    async with message.process(requeue=True):
                        while True:
                            try:
                                await save_click(event)
                                break
                            except (asyncpg.PostgresError, OSError, TimeoutError):
                                logger.exception('БД недоступна, повторим запись через 2 секунды')
                                await asyncio.sleep(2)
                except aio_pika.exceptions.ChannelInvalidStateError:
                    logger.warning('Канал закрылся до подтверждения, ожидаем повторную доставку')
    finally:
        await queue_client.close_queue()
        await close_db()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
