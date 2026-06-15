from django.contrib import admin
from django.urls import path
from core.views import serve_document
from core.pdf import generate_student_pdf

urlpatterns = [
    path('admin/', admin.site.urls),
    path('documents/serve/<int:doc_id>/', serve_document, name='serve_document'),
    path('students/<int:student_id>/pdf/', generate_student_pdf, name='generate_student_pdf'),
]
