# gunicorn_config.py
# Configuración para evitar crash en Render

workers = 2
worker_class = 'sync'
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 50

# Para manejar mejor los errores de MongoDB
preload_app = True

# Logs detallados
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Manejo de señales
graceful_timeout = 30