import base64
import json
import os
import urllib.error
import urllib.request


credentials = f'{os.environ["RABBITMQ_USER"]}:{os.environ["RABBITMQ_PASSWORD"]}'
authorization = base64.b64encode(credentials.encode()).decode()

for host in ['rabbit1', 'rabbit2', 'rabbit3']:
    request = urllib.request.Request(
        f'http://{host}:15672/api/queues/%2F/clicks',
        headers={'Authorization': f'Basic {authorization}'},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError):
        continue

    print(json.dumps({
        key: data.get(key)
        for key in ['name', 'type', 'leader', 'members', 'online', 'messages', 'messages_ready', 'messages_unacknowledged']
    }, indent=2))
    break
else:
    raise SystemExit('RabbitMQ management API is unavailable')
