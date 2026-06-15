from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from .models import Document

def serve_document(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)

    # Permission check: consultant sees own students, manager sees all
    if not request.user.groups.filter(name__in=['manager', 'admin']).exists():
        if doc.student.assigned_consultant != request.user:
            raise PermissionDenied("You can only access documents for your assigned students.")

    response = FileResponse(doc.file)
    response['X-Accel-Redirect'] = f'/protected/{doc.file.name}'
    response['Content-Disposition'] = f'inline; filename="{doc.file.name.split("/")[-1]}"'
    return response
