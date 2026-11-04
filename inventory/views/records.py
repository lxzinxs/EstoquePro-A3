from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from ..forms import (
    ProductForm,
    ScopedModelForm,
)
from ..models import (
    Location,
    Organization,
    Product,
    PurchaseLine,
    PurchaseOrder,
)
from ..services import (
    add_quote,
    audit,
    identifier,
    permit,
    save_product,
)
from .common import COLLECTIONS, PREMIUM, errors, page, tenant


@tenant
def listing(request, kind):
    if kind not in COLLECTIONS:
        raise Http404
    model, title, fields, _ = COLLECTIONS[kind]
    permit(
        request.a,
        "admin"
        if kind == "members"
        else "admin"
        if kind in ("ledger", "audit", "quotes", "schedules")
        else "member",
        write=False,
        premium=kind in PREMIUM,
    )
    query = (
        model.objects.filter(organization=request.a.organization)
        if model != PurchaseLine
        else model.objects.filter(order__organization=request.a.organization)
    )
    if kind == "products":
        query = query.filter(active=True).annotate(stock_quantity=Coalesce(Sum("lot__quantity"), 0))
        if request.GET.get("q"):
            query = query.filter(
                Q(name__icontains=request.GET["q"])
                | Q(sku__icontains=request.GET["q"])
                | Q(barcode=request.GET["q"])
            )
    if kind == "movements" and request.GET.get("product"):
        try:
            product_id = identifier(request.GET["product"])
        except ValidationError:
            return HttpResponse("Produto inválido.", status=400)
        query = query.filter(product_id=product_id)
    related = [field for field in fields if model._meta.get_field(field).many_to_one]
    if related:
        nested = [
            field + "__company"
            for field in related
            if model._meta.get_field(field).related_model is Location
        ]
        query = query.select_related(*related, *nested)
    total = query.count()
    from django.core.paginator import Paginator

    pagination = Paginator(query.order_by("-pk"), 50).get_page(request.GET.get("page"))
    rows = []
    for item in pagination:
        actions = []
        if kind == "products":
            actions = [
                (
                    "Registrar entrada",
                    reverse("movement") + "?" + urlencode({"product": item.pk}),
                ),
                ("Editar produto", reverse("edit-product", args=[item.pk])),
                ("Ajustar alerta", reverse("reorder-level", args=[item.pk])),
                ("Arquivar", reverse("action", args=["archive", item.pk])),
                (
                    "Histórico",
                    reverse("listing", args=["movements"]) + "?" + urlencode({"product": item.pk}),
                ),
            ]
            if request.a.role == "member":
                actions = [
                    action for action in actions if action[0] in ("Registrar entrada", "Histórico")
                ]
        if kind == "orders":
            actions = [
                ("Receber", reverse("action", args=["receive", item.pk])),
                ("Compartilhar", reverse("order-share", args=[item.pk])),
            ]
        if kind == "transfers" and item.status == "pending":
            actions = [("Confirmar", reverse("action", args=["confirm", item.pk]))]
        if kind == "ledger":
            actions = [("Baixar", reverse("payment", args=[item.pk]))]
        if kind == "counts" and item.status == "pending":
            actions = [("Fechar contagem", reverse("action", args=["count", item.pk]))]
        if kind == "jobs" and item.status == "done" and item.result_file:
            actions = [("Baixar", reverse("job-file", args=[item.pk]))]
        if kind == "members" and request.a.role in ("master", "creator"):
            actions = [("Alterar cargo", reverse("membership-edit", args=[item.pk]))]
        cells = [
            getattr(item, "get_" + f + "_display")()
            if callable(getattr(item, "get_" + f + "_display", None))
            else getattr(item, f)
            for f in fields
        ]
        if kind == "products":
            cells.append(item.stock_quantity)
        rows.append({"id": item.pk, "name": str(item), "cells": cells, "actions": actions})
    create = (
        reverse("new-record", args=[kind])
        if COLLECTIONS[kind][3]
        else reverse("add-member")
        if kind == "members"
        else None
    )
    return page(
        request,
        "inventory/list.html",
        {
            "title": title,
            "headers": [
                {
                    "sku": "Código",
                    "name": "Nome",
                    "price": "Preço (R$)",
                    "minimum": "Alerta quando",
                    "supplier": "Fornecedor",
                    "location": "Local",
                    "product": "Produto",
                    "quantity": "Quantidade",
                    "kind": "Tipo",
                    "unit_cost": "Custo unitário",
                    "note": "Motivo",
                    "actor": "Usuário",
                    "created_at": "Data",
                    "status": "Situação",
                    "amount": "Valor",
                    "due_date": "Vencimento",
                    "company": "Filial",
                    "code": "Lote",
                    "expiry": "Validade",
                    "user": "Usuário",
                    "role": "Perfil",
                }.get(f, f.replace("_", " ").capitalize())
                for f in fields
            ]
            + (["Saldo"] if kind == "products" else []),
            "rows": rows,
            "pagination": pagination,
            "total": total,
            "create": create,
            "kind": kind,
            "create_label": "Novo produto"
            if kind == "products"
            else "Adicionar membro"
            if kind == "members"
            else "Novo registro",
        },
    )


@tenant
def new_record(request, kind, pk=None):
    if kind not in COLLECTIONS or COLLECTIONS[kind][3] is None:
        raise Http404
    model, title, _, fields = COLLECTIONS[kind]
    permit(request.a, "member" if kind == "counts" else "admin", premium=kind in PREMIUM)
    if pk and kind != "products":
        raise Http404
    instance = (
        get_object_or_404(Product, organization=request.a.organization, pk=pk) if pk else None
    )
    Form = (
        ProductForm
        if kind == "products"
        else forms.modelform_factory(model, form=ScopedModelForm, fields=fields)
    )
    form = Form(
        request.POST if request.method == "POST" else None,
        organization=request.a.organization,
        instance=instance,
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                Organization.objects.select_for_update().get(pk=request.a.organization.pk)
                if kind == "products":
                    data = {
                        k: (v.pk if hasattr(v, "pk") else v) for k, v in form.cleaned_data.items()
                    }
                    save_product(request.a, data, pk)
                elif kind == "quotes":
                    d = form.cleaned_data
                    add_quote(
                        request.a,
                        d["product"].pk,
                        d["supplier"].pk,
                        d["round_key"],
                        d["price"],
                    )
                else:
                    item = form.save(commit=False)
                    if hasattr(item, "organization_id"):
                        item.organization = request.a.organization
                    if kind == "lines":
                        item.order = PurchaseOrder.objects.select_for_update().get(
                            pk=item.order_id, organization=request.a.organization
                        )
                        if item.order.status != "pending":
                            raise ValidationError("Pedido já recebido.")
                    if kind == "counts":
                        if (
                            item.lot.product_id != item.product_id
                            or item.lot.location_id != item.location_id
                        ):
                            raise ValidationError("Lote não pertence ao produto/local escolhido.")
                        item.actor = request.user
                    if kind == "schedules" and item.interval_hours < 1:
                        raise ValidationError("Intervalo mínimo de uma hora.")
                    item.full_clean()
                    item.save()
                    audit(request.a, kind + ".created", id=item.pk)
            messages.success(request, "Registro salvo.")
            return redirect("listing", kind=kind)
        except (ValidationError, IntegrityError) as e:
            errors(form, e)
    return page(
        request,
        "inventory/form.html",
        {
            "form": form,
            "title": title,
            "product_form": kind == "products",
            "is_edit": bool(pk),
        },
    )
