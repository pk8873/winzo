web: gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT app:app
worker: celery -A app.celery_app.celery worker --loglevel=info
