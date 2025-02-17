web: gunicorn --workers=2 --threads=4 --bind 0.0.0.0:$PORT src.server:app
worker: celery -A src.server.celery worker --loglevel=info