from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.urls import reverse

from ..models import (
    Audit,
    Category,
    Company,
    Job,
    Ledger,
    Location,
    Lot,
    Membership,
    Movement,
    Organization,
    Product,
    PurchaseLine,
    PurchaseOrder,
    Quote,
    Schedule,
    StockCount,
    Supplier,
    Transfer,
)
from ..services import (
    access_for,
    is_creator,
)

COLLECTIONS = {
    "products": (
        Product,
        "Produtos",
        ["sku", "name", "price", "minimum"],
        [
            "sku",
            "name",
            "category",
            "supplier",
            "barcode",
            "price",
            "minimum",
            "lead_days",
        ],
    ),
    "categories": (Category, "Categorias", ["name"], ["name"]),
    "suppliers": (
        Supplier,
        "Fornecedores",
        ["name", "email", "phone"],
        ["name", "email", "phone"],
    ),
    "companies": (Company, "Filiais", ["name"], ["name"]),
    "locations": (
        Location,
        "Locais e atendimento",
        ["name", "company", "kind"],
        ["name", "company", "kind"],
    ),
    "orders": (
        PurchaseOrder,
        "Pedidos de compra",
        ["id", "supplier", "location", "status"],
        ["supplier", "location"],
    ),
    "lines": (
        PurchaseLine,
        "Itens de pedido",
        ["order", "product", "quantity", "unit_cost"],
        ["order", "product", "quantity", "unit_cost", "lot_code", "expiry"],
    ),
    "ledger": (
        Ledger,
        "Financeiro",
        ["id", "kind", "description", "amount", "due_date"],
        ["kind", "description", "amount", "due_date"],
    ),
    "quotes": (
        Quote,
        "Cotações e preços",
        ["product", "supplier", "round_key", "price", "created_at"],
        ["product", "supplier", "round_key", "price"],
    ),
    "counts": (
        StockCount,
        "Inventário cego",
        ["id", "location", "product", "counted", "status"],
        ["location", "product", "lot", "counted"],
    ),
    "movements": (
        Movement,
        "Histórico completo",
        [
            "id",
            "product",
            "location",
            "kind",
            "quantity",
            "unit_cost",
            "note",
            "actor",
            "created_at",
        ],
        None,
    ),
    "lots": (
        Lot,
        "Lotes e validade",
        ["product", "location", "code", "expiry", "quantity"],
        None,
    ),
    "transfers": (
        Transfer,
        "Transferências",
        ["id", "product", "source", "destination", "quantity", "status"],
        None,
    ),
    "audit": (
        Audit,
        "Auditoria",
        ["id", "actor", "action", "details", "created_at"],
        None,
    ),
    "jobs": (
        Job,
        "Tarefas e arquivos",
        ["id", "kind", "status", "attempts", "error", "created_at"],
        None,
    ),
    "schedules": (
        Schedule,
        "Agendamento",
        ["kind", "interval_hours", "next_run", "enabled"],
        ["kind", "interval_hours", "next_run", "enabled"],
    ),
    "members": (Membership, "Equipe", ["id", "user", "role"], None),
}
PREMIUM = set(COLLECTIONS) - {"products", "categories", "movements", "lots", "jobs", "members"}


def navigation(a, current_path):
    premium = a.organization.billing_account.plan == "complete" or is_creator(a.user)
    rank = {"member": 0, "admin": 1, "master": 2, "creator": 3}[a.role]
    groups = [
        (
            "Estoque",
            "▣",
            [
                ("Produtos", "listing", "products", 0, False),
                ("Categorias", "listing", "categories", 0, False),
                ("Fornecedores", "listing", "suppliers", 0, True),
                ("Lotes e validade", "listing", "lots", 0, False),
                ("Histórico", "listing", "movements", 0, False),
            ],
        ),
        (
            "Compras",
            "▤",
            [
                ("Pedidos de compra", "listing", "orders", 0, True),
                ("Cotações e preços", "listing", "quotes", 1, True),
                ("Importar NF-e", "nfe", None, 1, True),
            ],
        ),
        (
            "Financeiro e análises",
            "↗",
            [
                ("Contas a pagar e receber", "listing", "ledger", 1, True),
                ("Análises e Curva ABC", "analysis", None, 1, True),
            ],
        ),
        (
            "Operações",
            "⇄",
            [
                ("Transferências", "listing", "transfers", 0, True),
                ("Nova transferência", "transfer", None, 0, True),
                ("Movimentação em lote", "batch", None, 0, True),
                ("Inventário cego", "listing", "counts", 0, True),
                ("Etiquetas", "labels", None, 0, True),
                ("Exportar CSV", "report", "csv", 0, False),
            ],
        ),
        (
            "Configurações",
            "⚙",
            [
                ("Filiais", "listing", "companies", 0, True),
                ("Locais e atendimento", "listing", "locations", 0, True),
                ("Equipe e membros", "listing", "members", 1, False),
                ("Adicionar membro", "add-member", None, 1, False),
                ("Novo negócio", "new-business", None, 2, True),
                ("Marca nos relatórios", "branding", None, 2, True),
                ("Auditoria", "listing", "audit", 1, True),
                ("Tarefas e arquivos", "listing", "jobs", 0, False),
                ("Agendamentos", "listing", "schedules", 1, True),
                ("Planos", "plans", None, 0, False),
                ("Assinatura", "subscription", None, 2, False),
                ("Alterar senha", "password_change", None, 0, False),
            ],
        ),
    ]
    result = []
    for label, icon, items in groups:
        links = []
        for title, route, arg, level, paid in items:
            if rank < level or (paid and not premium):
                continue
            url = reverse(route, args=[arg] if arg else [])
            links.append({"label": title, "url": url, "active": current_path == url})
        if links:
            result.append(
                {
                    "label": label,
                    "icon": icon,
                    "links": links,
                    "open": any(link["active"] for link in links)
                    or (current_path == "/" and label == "Estoque"),
                }
            )
    return result


def tenant(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        memberships = list(
            Membership.objects.filter(user=request.user).select_related("organization")
        )
        if is_creator(request.user):
            from types import SimpleNamespace

            memberships = [
                SimpleNamespace(organization=o, organization_id=o.pk)
                for o in Organization.objects.all()
            ]
        if not memberships:
            return render(request, "inventory/no_business.html")
        org_id = request.session.get("organization_id")
        member = next((m for m in memberships if m.organization_id == org_id), memberships[0])
        request.a = access_for(request.user, member.organization_id)
        request.tenant_context = {
            "org": request.a.organization,
            "role": request.a.role,
            "creator_access": is_creator(request.user),
            "complete_access": is_creator(request.user)
            or request.a.organization.billing_account.plan == "complete",
            "memberships": memberships,
            "nav_groups": navigation(request.a, request.path),
        }
        return view(request, *args, **kwargs)

    return wrapped


def page(request, template, context):
    return render(request, template, {**request.tenant_context, **context})


def errors(form, exc):
    form.add_error(
        None,
        " ".join(exc.messages)
        if isinstance(exc, ValidationError)
        else "Registro duplicado ou vínculo inválido.",
    )
