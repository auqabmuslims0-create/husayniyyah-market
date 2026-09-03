web: python scripts/init_db.py && flask db upgrade && SCHEDULER_ENABLED=1 gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300
