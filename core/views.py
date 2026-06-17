from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Document


@login_required
def serve_document(request, doc_id):
    """
    Serve documents securely using Nginx X-Accel-Redirect.
    The file is never read into Django memory — Nginx serves it directly.
    """
    doc = get_object_or_404(Document, id=doc_id)

    # Permission check: consultant sees own students, manager/admin sees all
    if not request.user.groups.filter(name__in=["manager", "admin"]).exists():
        if doc.student.assigned_consultant != request.user:
            raise PermissionDenied(
                "You can only access documents for your assigned students."
            )

    response = HttpResponse()
    # FIX: document_path no longer prefixes with "uploads/", so file.name is
    # already relative to MEDIA_ROOT. Nginx alias maps /protected/ to MEDIA_ROOT.
    response["X-Accel-Redirect"] = f"/protected/{doc.file.name}"
    response["Content-Type"] = ""
    response["Content-Disposition"] = (
        f'inline; filename="{doc.file.name.split("/")[-1]}"'
    )
    return response
