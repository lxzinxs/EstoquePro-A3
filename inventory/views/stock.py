from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import Http404, JsonResponse
from django.shortcuts import redirect

from ..forms import (
    JsonForm,
    MoveForm,
    ScopedModelForm,
)
from ..models import (
    Audit,
    Product,
    Transfer,
)
from ..services import (
    archive_product,
    batch_move,
    close_count,
    confirm_transfer,
    create_transfer,
    move,
    permit,
    receive_order,
    set_reorder_level,
)
from .common import errors, page, tenant


@tenant
def dashboard(request):
    products = list(
        Product.objects.filter(organization=request.a.organization, active=True).annotate(
            stock_quantity=Coalesce(Sum("lot__quantity"), 0)
        )
    )
    rows = [
        {"product": p, "quantity": p.stock_quantity, "low": p.stock_quantity <= p.minimum}
        for p in products
    ]
    return page(
        request,
        "inventory/dashboard.html",
        {
            "rows": rows,
            "units": sum(r["quantity"] for r in rows),
            "value": sum((r["quantity"] * r["product"].price for r in rows), Decimal("0")),
            "low": sum(r["low"] for r in rows),
            "events": Audit.objects.filter(
                organization=request.a.organization, action__startswith="transfer."
            ).order_by("-id")[:10],
        },
    )


@tenant
def movement(request):
    form = MoveForm(
        request.POST if request.method == "POST" else None, organization=request.a.organization
    )
    selected = request.GET.get("product", "")
    if (
        request.method == "GET"
        and selected.isdigit()
        and len(selected) < 19
        and Product.objects.filter(
            pk=selected, organization=request.a.organization, active=True
        ).exists()
    ):
        form.initial["product"] = selected
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            move(
                request.a,
                d["product"].pk,
                d["location"].pk,
                d["kind"],
                d["quantity"],
                d["note"],
                d["unit_cost"],
                d["lot_code"],
                d["expiry"],
            )
            messages.success(request, "Movimentação registrada.")
            return redirect("listing", kind="movements")
        except (ValidationError, IntegrityError) as e:
            errors(form, e)
    return page(request, "inventory/form.html", {"form": form, "title": "Entrada / saída FEFO"})


@tenant
def batch(request):
    permit(request.a, premium=True)
    form = JsonForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            batch_move(request.a, form.cleaned_data["lines"])
            messages.success(request, "Lote de movimentações concluído.")
            return redirect("listing", kind="movements")
        except (ValidationError, IntegrityError, TypeError, KeyError) as e:
            errors(
                form,
                e
                if isinstance(e, ValidationError)
                else ValidationError("Formato das linhas inválido."),
            )
    return page(
        request,
        "inventory/form.html",
        {"form": form, "title": "Movimentação em lote atômica"},
    )


@tenant
def transfer(request):
    permit(request.a, premium=True)
    Form = forms.modelform_factory(
        Transfer,
        form=ScopedModelForm,
        fields=["product", "source", "destination", "quantity"],
    )
    form = Form(
        request.POST if request.method == "POST" else None, organization=request.a.organization
    )
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            create_transfer(
                request.a,
                d["product"].pk,
                d["source"].pk,
                d["destination"].pk,
                d["quantity"],
            )
            return redirect("listing", kind="transfers")
        except (ValidationError, IntegrityError) as e:
            errors(form, e)
    return page(
        request,
        "inventory/form.html",
        {"form": form, "title": "Enviar transferência para confirmação"},
    )


@tenant
def action(request, kind, pk):
    handlers = {
        "archive": archive_product,
        "receive": receive_order,
        "confirm": confirm_transfer,
        "count": close_count,
    }
    if kind not in handlers:
        raise Http404
    form = forms.Form(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        try:
            handlers[kind](request.a, pk)
            messages.success(request, "Operação concluída.")
            return redirect("dashboard")
        except (ValidationError, IntegrityError) as e:
            errors(form, e)
    return page(
        request,
        "inventory/form.html",
        {
            "form": form,
            "title": "Confirmar operação",
            "help": "Confirme para aplicar a operação. Alterações ficam registradas na auditoria.",
        },
    )


@tenant
def barcode(request):
    permit(request.a, write=False, premium=True)
    product = (
        Product.objects.filter(
            organization=request.a.organization,
            active=True,
            barcode=request.GET.get("code", ""),
        )
        .exclude(barcode="")
        .first()
    )
    if not product:
        return JsonResponse({"error": "Código não cadastrado neste negócio."}, status=404)
    return JsonResponse({"id": product.pk, "name": product.name})


@tenant
def notifications(request):
    permit(request.a, write=False)
    try:
        since = min(9223372036854775807, max(0, int(request.GET.get("since", "0"))))
    except ValueError:
        since = 0
    events = Audit.objects.filter(
        organization=request.a.organization,
        action__startswith="transfer.",
        id__gt=since,
    ).order_by("id")[:100]
    return JsonResponse(
        {"events": [{"id": e.pk, "action": e.action, "details": e.details} for e in events]}
    )


@tenant
def reorder_level(request, pk):
    from django import forms
    from django.shortcuts import get_object_or_404

    permit(request.a, "admin")
    product = get_object_or_404(Product, pk=pk, organization=request.a.organization, active=True)
    form = forms.Form(
        request.POST if request.method == "POST" else None, initial={"minimum": product.minimum}
    )
    form.fields["minimum"] = forms.IntegerField(
        label="Avisar quando o saldo for de",
        min_value=0,
        max_value=999999999,
        help_text="Ex.: 1 mostra Repor quando houver 1 unidade ou menos. Use 0 para avisar apenas quando o estoque acabar. O saldo não será alterado.",
    )
    if request.method == "POST" and form.is_valid():
        set_reorder_level(request.a, pk, form.cleaned_data["minimum"])
        messages.success(request, "Alerta de reposição atualizado.")
        return redirect("listing", kind="products")
    return page(
        request,
        "inventory/form.html",
        {"form": form, "title": "Alerta de reposição · " + product.name},
    )
