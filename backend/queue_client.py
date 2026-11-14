import asyncio
from urllib.parse import quote

import aio_pika

from config import QUEUE_NAME, RABBIT_USER, RABBIT_PASS


connection = None
channel = None
queue = None


async def connect_queue():
    global connection, channel, queue
    user = quote(RABBIT_USER, safe='')
    password = quote(RABBIT_PASS, safe='')
    connection = await aio_pika.connect_robust(
        f'amqp://{user}:{password}@amqp:5672/',
        timeout=15,
        reconnect_interval=2,
    )
    channel = await connection.channel(publisher_confirms=True)
    await channel.set_qos(prefetch_count=10)
    queue = await channel.declare_queue(
        QUEUE_NAME,
        durable=True,
        arguments={'x-queue-type': 'quorum', 'x-quorum-initial-group-size': 3},
    )


async def publish_click(event):
    await asyncio.wait_for(connection.ready(), timeout=10)
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=event.model_dump_json().encode(),
            content_type='application/json',
            message_id=str(event.event_id),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=QUEUE_NAME,
        mandatory=True,
        timeout=10,
    )


async def close_queue():
    if connection is not None:
        await connection.close()
