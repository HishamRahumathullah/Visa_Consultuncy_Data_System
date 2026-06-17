from django.http import JsonResponse
from django.urls import path
from django.contrib import admin
from core.views import serve_document
from core.pdf import generate_student_pdf

def healthcheck(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', healthcheck, name='healthcheck'),
    path('documents/serve/<int:doc_id>/', serve_document, name='serve_document'),
    path('students/<int:student_id>/pdf/', generate_student_pdf, name='generate_student_pdf'),
]
