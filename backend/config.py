import os


DB_HOSTS = os.environ.get('DB_HOSTS', 'postgres,postgres_standby').split(',')
DB_NAME = os.environ.get('POSTGRES_DB', 'swag')
DB_USER = os.environ.get('APP_DB_USER', 'swag')
DB_PASS = os.environ['APP_DB_PASSWORD']
RABBIT_USER = os.environ.get('RABBITMQ_USER', 'swag')
RABBIT_PASS = os.environ['RABBITMQ_PASSWORD']
ADMIN_TOKEN = os.environ['ADMIN_TOKEN']
PROXY_TOKEN = os.environ.get('PROXY_TOKEN', '')
QUEUE_NAME = 'clicks'
