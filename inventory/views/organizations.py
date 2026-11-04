from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from ..services import (
    access_for,
    audit,
    create_business,
    permit,
)
from .common import errors, page, tenant


@tenant
@require_POST
def switch(request):
    a = access_for(request.user, request.POST.get("organization"))
    request.session["organization_id"] = a.organization.pk
    return redirect("dashboard")


@tenant
def business(request):
    permit(request.a, "master", premium=True)
    form = forms.Form(request.POST if request.method == "POST" else None)
    form.fields["name"] = forms.CharField(label="Nome do novo negócio", max_length=120)
    if request.method == "POST" and form.is_valid():
        try:
            org = create_business(request.a, form.cleaned_data["name"])
            request.session["organization_id"] = org.pk
            return redirect("dashboard")
        except (ValidationError, IntegrityError) as e:
            errors(form, e)
    return page(
        request,
        "inventory/form.html",
        {"form": form, "title": "Novo negócio com dados isolados"},
    )


@tenant
def branding(request):
    permit(request.a, "master", premium=True)
    form = forms.Form(request.POST if request.method == "POST" else None, request.FILES or None)
    form.fields["logo"] = forms.ImageField(label="Logo PNG ou JPEG")
    if request.method == "POST" and form.is_valid():
        import uuid

        from django.conf import settings
        from PIL import Image

        upload = form.cleaned_data["logo"]
        if upload.size > 2 * 1024 * 1024:
            form.add_error("logo", "Tamanho máximo de 2 MB.")
        else:
            try:
                image = Image.open(upload)
                if image.format not in ("PNG", "JPEG") or image.width > 2000 or image.height > 2000:
                    raise ValueError
                path = (
                    settings.PRIVATE_ROOT
                    / str(request.a.organization.pk)
                    / ("logo-" + uuid.uuid4().hex + ".png")
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                image.convert("RGB").save(path, "PNG")
                path.chmod(0o600)
                request.a.organization.logo_file = str(path.relative_to(settings.PRIVATE_ROOT))
                request.a.organization.save(update_fields=["logo_file"])
                audit(request.a, "brand.updated")
                messages.success(request, "Marca atualizada.")
                return redirect("dashboard")
            except (OSError, ValueError):
                form.add_error("logo", "Use PNG/JPEG de até 2000 x 2000 pixels.")
    return page(request, "inventory/form.html", {"form": form, "title": "Marca nos relatórios"})
