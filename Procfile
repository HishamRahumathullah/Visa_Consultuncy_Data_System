web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn visa_consultancy.wsgi --bind 0.0.0.0:$PORT --workers 3 --timeout 60
