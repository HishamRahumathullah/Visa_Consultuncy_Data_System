import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "visa_consultancy.settings")
application = get_wsgi_application()
app = application  # ← ADD THIS
