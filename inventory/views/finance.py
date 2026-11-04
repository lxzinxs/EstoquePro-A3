from datetime import date
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from ..forms import (
    NfeForm,
    PaymentForm,
)
from ..integrations import import_nfe
from ..models import (
    Ledger,
    Location,
    Product,
    PurchaseOrder,
)
from ..reports import export
from ..services import (
    analytics,
    pay,
    permit,
    reorder,
)
from .common import errors, page, tenant


@tenant
def payment(request, pk):
    permit(request.a, "admin", premium=True)
    get_object_or_404(Ledger, organization=request.a.organization, pk=pk)
    form = PaymentForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            pay(request.a, pk, form.cleaned_data["value"], form.cleaned_data["date"])
            return redirect("listing", kind="ledger")
        except (ValidationError, IntegrityError) as e:
            errors(form, e)
    return page(
        request,
        "inventory/form.html",
        {"form": form, "title": "Registrar pagamento / recebimento"},
    )


@tenant
def nfe(request):
    permit(request.a, "admin", premium=True)
    form = NfeForm(
        request.POST if request.method == "POST" else None,
        request.FILES or None,
        organization=request.a.organization,
    )
    if request.method == "POST" and form.is_valid():
        try:
            import_nfe(
                request.a,
                form.cleaned_data["xml"].read(2 * 1024 * 1024 + 1),
                form.cleaned_data["location"].pk,
            )
            messages.success(request, "NF-e importada com estoque e contas a pagar.")
            return redirect("listing", kind="ledger")
        except (ValidationError, IntegrityError) as e:
            errors(form, e)
    return page(
        request,
        "inventory/form.html",
        {
            "form": form,
            "title": "Importar NF-e (XML)",
            "help": "Produtos devem estar cadastrados com o mesmo código cProd. Importação duplicada é recusada.",
        },
    )


@tenant
def analysis(request):
    permit(request.a, "admin", write=False, premium=True)
    form = forms.Form(request.GET if request.method == "GET" else None)
    form.fields["start"] = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Início"
    )
    form.fields["end"] = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Fim"
    )
    data = None
    if form.is_valid():
        try:
            data = analytics(request.a, form.cleaned_data["start"], form.cleaned_data["end"])
        except ValidationError as e:
            errors(form, e)
    return page(
        request,
        "inventory/analysis.html",
        {
            "form": form,
            "data": data,
            "locations": Location.objects.filter(organization=request.a.organization),
        },
    )


@tenant
def report(request, fmt):
    if fmt not in ("csv", "xlsx", "pdf"):
        raise Http404
    try:
        start = date.fromisoformat(request.GET["start"]) if request.GET.get("start") else None
        end = date.fromisoformat(request.GET["end"]) if request.GET.get("end") else None
        data, mime = export(request.a, fmt, start, end)
    except (ValueError, ValidationError):
        return HttpResponse("Período ou formato inválido.", status=400)
    return HttpResponse(
        data,
        content_type=mime,
        headers={"Content-Disposition": f'attachment; filename="estoquepro.{fmt}"'},
    )


@tenant
def share_order(request, pk):
    permit(request.a, "admin", write=False, premium=True)
    order = get_object_or_404(PurchaseOrder, organization=request.a.organization, pk=pk)
    text = f"EstoquePro / Pedido #{order.pk}\n" + "\n".join(
        f"{line.product.sku}: {line.quantity} x R$ {line.unit_cost}"
        for line in order.lines.select_related("product")
    )
    phone = "".join(c for c in order.supplier.phone if c.isdigit())
    return page(
        request,
        "inventory/share.html",
        {
            "text": text,
            "share_url": "https://wa.me/" + phone + "?" + urlencode({"text": text}),
        },
    )


@tenant
def labels(request):
    permit(request.a, write=False, premium=True)
    import io

    from reportlab.graphics.barcode import code128
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas

    out = io.BytesIO()
    c = Canvas(out, pagesize=A4)
    y = 800
    for p in Product.objects.filter(organization=request.a.organization, active=True).exclude(
        barcode=""
    ):
        if y < 100:
            c.showPage()
            y = 800
        if len(p.barcode) > 32:
            continue
        c.drawString(30, y, p.name[:60])
        code128.Code128(p.barcode, barHeight=35, barWidth=0.6).drawOn(c, 30, y - 45)
        c.drawString(30, y - 60, p.barcode)
        y -= 100
    c.save()
    return HttpResponse(
        out.getvalue(),
        content_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="etiquetas.pdf"'},
    )


@tenant
@require_POST
def suggested_order(request, pk):
    try:
        order = reorder(request.a, pk, request.POST.get("location"))
        return redirect("order-share", pk=order.pk)
    except (ValidationError, IntegrityError) as exc:
        messages.error(
            request,
            " ".join(exc.messages)
            if isinstance(exc, ValidationError)
            else "Não foi possível criar o pedido.",
        )
        return redirect("analysis")
