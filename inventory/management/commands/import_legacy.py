import hashlib
import json
import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from inventory.models import (
    Audit,
    Category,
    Company,
    LegacyImport,
    Location,
    Lot,
    Membership,
    Movement,
    Organization,
    Product,
    Schedule,
    Supplier,
)
from inventory.services import month_after


class Command(BaseCommand):
    help = (
        "Importa cópia consistente do SQLite legado, sem alterar a origem. Reexecução idempotente."
    )

    def add_arguments(self, p):
        p.add_argument("source")
        p.add_argument("--name", default="Negócio legado")

    @transaction.atomic
    def handle(self, *args, **opts):
        source = Path(opts["source"]).resolve()
        if not source.is_file():
            raise CommandError("Arquivo de origem inexistente.")
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = Path(temporary) / "snapshot.sqlite3"
            with (
                sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original,
                sqlite3.connect(snapshot) as target,
            ):
                original.backup(target)
            with sqlite3.connect(snapshot) as db:
                db.row_factory = sqlite3.Row
                try:
                    queries = {
                        "users": "SELECT * FROM users ORDER BY id",
                        "categories": "SELECT * FROM categories ORDER BY id",
                        "suppliers": "SELECT * FROM suppliers ORDER BY id",
                        "products": "SELECT * FROM products ORDER BY id",
                        "movements": "SELECT * FROM movements ORDER BY id",
                    }
                    data = {
                        table: [dict(row) for row in db.execute(query)]
                        for table, query in queries.items()
                    }
                except sqlite3.DatabaseError:
                    raise CommandError("Banco legado incompatível.") from None
        digest = hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        prior = LegacyImport.objects.filter(digest=digest).first()
        if prior:
            self.stdout.write(f"Importação já existente: organização {prior.organization_id}.")
            return
        User = get_user_model()
        if User.objects.filter(username__in=[u["username"] for u in data["users"]]).exists():
            raise CommandError(
                "Há nome de usuário já usado no Django. Nenhuma conta será sobrescrita; resolva o conflito antes de importar."
            )
        org = Organization.objects.create(
            name=opts["name"], trial_ends_at=month_after(timezone.now())
        )
        company = Company.objects.create(organization=org, name=opts["name"])
        location = Location.objects.create(organization=org, company=company, name="Principal")
        users = {}
        categories = {}
        suppliers = {}
        products = {}
        for i, row in enumerate(data["users"]):
            salt, digest_hash = row["password_hash"].split(":", 1)
            u = User.objects.create(
                username=row["username"],
                password=f"legacy_pbkdf2_sha256$260000${salt}${digest_hash}",
            )
            users[row["id"]] = u
            Membership.objects.create(
                organization=org, user=u, role="master" if i == 0 else "member"
            )
        for row in data["categories"]:
            categories[row["id"]] = Category.objects.create(organization=org, name=row["name"])
        for row in data["suppliers"]:
            suppliers[row["id"]] = Supplier.objects.create(organization=org, name=row["name"])
        for row in data["products"]:
            p = Product.objects.create(
                organization=org,
                sku=row["sku"],
                name=row["name"],
                category=categories[row["category_id"]],
                supplier=suppliers.get(row["supplier_id"]),
                price=Decimal(row["price_cents"]) / 100,
                minimum=row["minimum"],
                active=bool(row["active"]),
            )
            products[row["id"]] = p
            Lot.objects.create(
                organization=org,
                product=p,
                location=location,
                code="LEGADO",
                quantity=row["quantity"],
            )
        for row in data["movements"]:
            stamp = parse_datetime(row["created_at"])
            if stamp and timezone.is_naive(stamp):
                stamp = timezone.make_aware(stamp, __import__("datetime").timezone.utc)
            Movement.objects.create(
                organization=org,
                product=products[row["product_id"]],
                location=location,
                actor=users[row["user_id"]],
                kind="entry" if row["kind"] == "entrada" else "exit",
                purpose="legacy",
                quantity=row["quantity"],
                note=row["note"],
                created_at=stamp or timezone.now(),
                allocations=[{"legacy_balance_after": row["balance_after"]}],
            )
        LegacyImport.objects.create(organization=org, digest=digest)
        Audit.objects.create(
            organization=org,
            action="legacy.imported",
            details={"products": len(products), "costs": "unavailable"},
        )
        Schedule.objects.create(organization=org, kind="backup", interval_hours=24)
        self.stdout.write(
            f"Importados {len(products)} produtos e {len(data['movements'])} eventos para organização {org.pk}. Custos antigos não existiam e não foram inventados."
        )
