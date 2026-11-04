from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from ..models import (
    Job,
)
from ..services import (
    audit,
    permit,
)
from .common import tenant


@tenant
@require_POST
def queue(request, kind):
    if kind not in ("report", "backup", "briefing"):
        raise Http404
    permit(request.a, "master" if kind == "backup" else "admin", premium=kind != "backup")
    job = Job.objects.create(
        organization=request.a.organization,
        kind=kind,
        requested_by=request.user,
        payload={"format": "pdf"},
    )
    audit(request.a, "job.queued", id=job.pk, kind=kind)
    return redirect("listing", kind="jobs")


@tenant
def job_file(request, pk):
    job = get_object_or_404(Job, pk=pk, organization=request.a.organization, status="done")
    permit(request.a, "master" if job.kind == "backup" else "admin", write=False)
    from django.conf import settings

    path = (settings.PRIVATE_ROOT / job.result_file).resolve()
    if not path.is_relative_to(settings.PRIVATE_ROOT.resolve()) or not path.is_file():
        raise Http404
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)
