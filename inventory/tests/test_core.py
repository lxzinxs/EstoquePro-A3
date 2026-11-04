import io
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connections, transaction
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone

from ..integrations import import_nfe
from ..jobs import claim, enqueue_due, perform
from ..models import (
    Category,
    Company,
    Creator,
    Job,
    Ledger,
    Location,
    LoginThrottle,
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
)
from ..reports import export
from ..services import (
    Access,
    access_for,
    add_member,
    add_quote,
    analytics,
    batch_move,
    change_member,
    close_count,
    confirm_transfer,
    create_business,
    create_transfer,
    month_after,
    move,
    pay,
    permit,
    quantity,
    receive_order,
    register_business,
    reorder,
    save_product,
    scoped,
)


class InventoryFixture:
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "master", "master@example.test", "StrongTestPass!123"
        )
        self.org = Organization.objects.create(
            name="Empresa A",
            plan="complete",
            trial_ends_at=month_after(timezone.now()),
            paid_until=month_after(timezone.now(), 12),
        )
        Membership.objects.create(user=self.user, organization=self.org, role="master")
        self.a = access_for(self.user, self.org.pk)
        self.company = Company.objects.create(organization=self.org, name="Filial A")
        self.location = Location.objects.create(
            organization=self.org, company=self.company, name="A"
        )
        self.category = Category.objects.create(organization=self.org, name="Categoria")
        self.supplier = Supplier.objects.create(organization=self.org, name="Fornecedor")
        self.product = save_product(
            self.a,
            dict(
                sku="A1",
                name="Produto",
                category=self.category.pk,
                supplier=self.supplier.pk,
                price="20.00",
                minimum=3,
            ),
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["organization_id"] = self.org.pk
        session.save()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CoreTests(InventoryFixture, TransactionTestCase):
    def entry(self, qty=10, cost="10", code="L1", expiry=None):
        return move(
            self.a,
            self.product.pk,
            self.location.pk,
            "entry",
            qty,
            "Recebimento",
            cost,
            code,
            expiry,
        )

    def test_postgresql_backend(self):
        self.assertEqual(connections["default"].vendor, "postgresql")

    def test_registration_isolates_businesses(self):
        u, o = register_business("new.user", "AnotherStrong!123", "new@example.test", "Empresa B")
        self.assertNotEqual(o, self.org)
        self.assertEqual(Membership.objects.get(user=u).role, "master")
        with self.assertRaises(PermissionDenied):
            access_for(u, self.org.pk)
        self.client.force_login(u)
        response = self.client.get("/list/products/")
        self.assertNotContains(response, "<td>Produto</td>", html=True)
        self.assertEqual(response.status_code, 200)

    def test_tenant_reference_blocked(self):
        other = Organization.objects.create(name="B", trial_ends_at=month_after(timezone.now()))
        foreign = Category.objects.create(organization=other, name="Outro")
        with self.assertRaises(ValidationError):
            save_product(self.a, dict(sku="X", name="X", category=foreign.pk, price=0, minimum=0))
        with self.assertRaises(ValidationError):
            scoped(Product, Access(other, self.user, "master"), self.product.pk)

    def test_role_restrictions_and_last_master(self):
        member = add_member(self.a, "member", "m@example.test", "StrongMember!123", "member")
        access = access_for(member, self.org.pk)
        with self.assertRaises(PermissionDenied):
            save_product(
                access,
                dict(sku="X", name="X", category=self.category.pk, price=0, minimum=0),
            )
        self.entry()
        move(access, self.product.pk, self.location.pk, "exit", 1, "Consumo")
        with self.assertRaises(ValidationError):
            change_member(self.a, Membership.objects.get(user=self.user).pk, remove=True)
        self.client.force_login(member)
        self.assertEqual(self.client.get("/list/audit/").status_code, 403)
        self.assertEqual(self.client.get("/list/members/").status_code, 403)

    def test_creator_exclusive_global_unlimited(self):
        creator = get_user_model().objects.create_user(
            "Lxzinxs", password="SyntheticOnly!123", is_superuser=True, is_staff=True
        )
        Creator.objects.create(user=creator)
        self.org.plan = "basic"
        self.org.trial_ends_at = timezone.now() - timedelta(days=5)
        self.org.save()
        access = access_for(creator, self.org.pk)
        self.assertEqual(access.role, "creator")
        permit(access, "master", premium=True)
        self.client.force_login(creator)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertContains(self.client.get("/"), "Criador")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Creator.objects.create(pk=2, user=self.user)
        self.client.force_login(self.user)
        self.assertNotEqual(self.client.get("/admin/").status_code, 200)

    def test_trial_calendar_and_expiration(self):
        self.org.plan = "basic"
        self.org.trial_ends_at = timezone.now() - timedelta(seconds=1)
        self.org.save()
        with self.assertRaises(PermissionDenied):
            self.entry()
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/report/csv/").status_code, 200)
        from datetime import datetime
        from datetime import timezone as dtz

        self.assertEqual(month_after(datetime(2026, 1, 31, tzinfo=dtz.utc)).day, 28)

    def test_basic_quota_and_premium_gate(self):
        self.org.plan = "basic"
        self.org.save()
        for i in range(49):
            Product.objects.create(
                organization=self.org, sku=f"Q{i}", name="Quota", category=self.category
            )
        with self.assertRaises(ValidationError):
            save_product(
                self.a,
                dict(
                    sku="LAST",
                    name="Last",
                    category=self.category.pk,
                    price=0,
                    minimum=0,
                ),
            )
        with self.assertRaises(ValidationError):
            add_member(self.a, "second", "s@example.test", "StrongSecond!123", "member")
        self.assertEqual(self.client.get("/analysis/").status_code, 403)
        self.assertEqual(self.client.get("/new/suppliers/").status_code, 403)

    def test_weighted_average_and_rollback(self):
        self.entry(10, "10")
        self.entry(10, "20", code="L2")
        self.product.refresh_from_db()
        self.assertEqual(self.product.average_cost, Decimal("15"))
        with self.assertRaises(ValidationError):
            move(self.a, self.product.pk, self.location.pk, "exit", 21, "Erro")
        self.assertEqual(quantity(self.product), 20)
        self.assertEqual(Movement.objects.count(), 2)

    def test_fefo_excludes_expired(self):
        today = timezone.localdate()
        self.entry(3, "10", "vencido", today - timedelta(days=1))
        self.entry(4, "10", "primeiro", today + timedelta(days=1))
        self.entry(5, "10", "segundo", today + timedelta(days=5))
        self.entry(6, "10", "sem-validade")
        event = move(self.a, self.product.pk, self.location.pk, "exit", 6, "Consumo")
        self.assertEqual([a["code"] for a in event.allocations], ["primeiro", "segundo"])
        self.assertEqual(Lot.objects.get(code="vencido").quantity, 3)
        with self.assertRaises(ValidationError):
            move(
                self.a,
                self.product.pk,
                self.location.pk,
                "exit",
                10,
                "Sem saldo válido",
            )

    def test_batch_all_or_nothing(self):
        self.entry(5)
        lines = [
            dict(
                product_id=self.product.pk,
                location_id=self.location.pk,
                kind="exit",
                qty=3,
                note="Lote",
            ),
            dict(
                product_id=self.product.pk,
                location_id=self.location.pk,
                kind="exit",
                qty=3,
                note="Lote",
            ),
        ]
        with self.assertRaises(ValidationError):
            batch_move(self.a, lines)
        self.assertEqual(quantity(self.product), 5)
        self.assertEqual(Movement.objects.count(), 1)

    def test_concurrent_exits(self):
        self.entry(5)
        uid, oid, pid, lid = (
            self.user.pk,
            self.org.pk,
            self.product.pk,
            self.location.pk,
        )

        def attempt(_):
            connections.close_all()
            try:
                a = access_for(get_user_model().objects.get(pk=uid), oid)
                move(a, pid, lid, "exit", 4, "Saída concorrente")
                return True
            except ValidationError:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            result = list(executor.map(attempt, range(2)))
        self.assertEqual(result.count(True), 1)
        self.assertEqual(quantity(self.product), 1)

    def test_receive_order_idempotent_and_payable(self):
        order = PurchaseOrder.objects.create(
            organization=self.org, supplier=self.supplier, location=self.location
        )
        PurchaseLine.objects.create(
            order=order, product=self.product, quantity=3, unit_cost=Decimal("8")
        )
        receive_order(self.a, order.pk)
        receive_order(self.a, order.pk)
        self.assertEqual(quantity(self.product), 3)
        self.assertEqual(Ledger.objects.get().amount, Decimal("24"))
        self.assertEqual(Movement.objects.count(), 1)

    def test_transfer_confirmation_no_double_credit(self):
        destination = Location.objects.create(organization=self.org, company=self.company, name="B")
        self.entry(10)
        transfer = create_transfer(self.a, self.product.pk, self.location.pk, destination.pk, 4)
        self.assertEqual(quantity(self.product, self.location), 6)
        self.assertEqual(quantity(self.product, destination), 0)
        self.assertEqual(quantity(self.product, owned=True), 10)
        confirm_transfer(self.a, transfer.pk)
        confirm_transfer(self.a, transfer.pk)
        self.assertEqual(quantity(self.product, destination), 4)
        self.assertEqual(Movement.objects.count(), 3)

    def test_ledger_partial_payments_and_cash(self):
        ledger = Ledger.objects.create(
            organization=self.org,
            kind="payable",
            description="Compra",
            amount=100,
            due_date=timezone.localdate(),
        )
        pay(self.a, ledger.pk, "30", timezone.localdate())
        with self.assertRaises(ValidationError):
            pay(self.a, ledger.pk, "71", timezone.localdate())
        pay(self.a, ledger.pk, "70", timezone.localdate())
        result = analytics(self.a)
        self.assertEqual(result["cash"], Decimal("-100"))

    def test_quotes_limit_three_and_history(self):
        for i in range(3):
            supplier = Supplier.objects.create(organization=self.org, name=f"F{i}")
            add_quote(self.a, self.product.pk, supplier.pk, "rodada", "10")
        with self.assertRaises(ValidationError):
            add_quote(self.a, self.product.pk, self.supplier.pk, "rodada", "9")
        add_quote(self.a, self.product.pk, self.supplier.pk, "outra", "9")
        self.assertEqual(Quote.objects.count(), 4)

    def test_stockcount_closure_idempotent(self):
        self.entry(10)
        lot = Lot.objects.get()
        count = StockCount.objects.create(
            organization=self.org,
            product=self.product,
            location=self.location,
            lot=lot,
            counted=7,
            actor=self.user,
        )
        close_count(self.a, count.pk)
        close_count(self.a, count.pk)
        self.assertEqual(quantity(self.product), 7)
        self.assertEqual(Movement.objects.count(), 2)

    def test_exports_real_formats_and_formula_safety(self):
        self.product.name = '=HYPERLINK("test")'
        self.product.save()
        self.entry()
        raw, mime = export(self.a, "xlsx")
        from openpyxl import load_workbook

        book = load_workbook(io.BytesIO(raw))
        self.assertTrue(book.active.cell(2, 2).value.startswith("'="))
        pdf, _ = export(self.a, "pdf")
        self.assertTrue(pdf.startswith(b"%PDF-"))
        csv, _ = export(self.a, "csv")
        self.assertIn(b"'=HYPERLINK", csv)

    def test_nfe_import_atomic_and_duplicate(self):
        key = "1" * 44
        xml = f'<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{key}"><ide><nNF>42</nNF></ide><det><prod><cProd>A1</cProd><qCom>2</qCom><vUnCom>10</vUnCom></prod></det><total><ICMSTot><vNF>20</vNF></ICMSTot></total></infNFe></NFe></nfeProc>'.encode()
        import_nfe(self.a, xml, self.location.pk)
        self.assertEqual(quantity(self.product), 2)
        self.assertEqual(Ledger.objects.get().amount, Decimal("20"))
        with self.assertRaises(ValidationError):
            import_nfe(self.a, xml, self.location.pk)
        self.assertEqual(Movement.objects.count(), 1)
        with self.assertRaises(ValidationError):
            import_nfe(
                self.a,
                b'<!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><a>&x;</a>',
                self.location.pk,
            )

    def test_jobs_export_backup_and_isolated_download(self):
        self.entry()
        with (
            tempfile.TemporaryDirectory() as temporary,
            override_settings(PRIVATE_ROOT=__import__("pathlib").Path(temporary)),
        ):
            job = Job.objects.create(
                organization=self.org,
                kind="report",
                requested_by=self.user,
                payload={"format": "pdf"},
            )
            claimed = claim()
            self.assertEqual(claimed[0], job.pk)
            self.assertTrue(perform(*claimed))
            job.refresh_from_db()
            self.assertEqual(self.client.get(f"/files/{job.pk}/").status_code, 200)
            backup = Job.objects.create(
                organization=self.org, kind="backup", requested_by=self.user
            )
            claimed = claim()
            self.assertEqual(claimed[0], backup.pk)
            self.assertTrue(perform(*claimed))
            backup.refresh_from_db()
            data = json.loads(
                (__import__("pathlib").Path(temporary) / backup.result_file).read_text()
            )
            self.assertNotIn("auth.User", data)
            self.assertIn("inventory.Product", data)
            Schedule.objects.create(organization=self.org, kind="briefing", interval_hours=24)
            enqueue_due()
            enqueue_due()
            self.assertEqual(Job.objects.filter(kind="briefing").count(), 1)

    def test_csrf_password_reset_and_no_get_mutation(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.user)
        self.assertEqual(c.post("/move/", {}).status_code, 403)
        before = Product.objects.count()
        self.client.get(f"/action/archive/{self.product.pk}/")
        self.assertEqual(Product.objects.count(), before)
        self.client.logout()
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertEqual(
            self.client.post(
                "/accounts/password_reset/", {"email": "master@example.test"}
            ).status_code,
            302,
        )
        from django.core import mail

        self.assertEqual(len(mail.outbox), 1)

    def test_new_business_inherits_subscription_and_isolates_data(self):
        org = create_business(self.a, "Outro negócio")
        other = access_for(self.user, org.pk)
        self.assertEqual(Product.objects.filter(organization=org).count(), 0)
        permit(other, premium=True)
        self.org.paid_until = timezone.now() - timedelta(seconds=1)
        self.org.save()
        with self.assertRaises(PermissionDenied):
            permit(other, premium=True)
        with self.assertRaises(PermissionDenied):
            move(
                other,
                self.product.pk,
                self.location.pk,
                "exit",
                1,
                "Ataque de referência",
            )

    def test_cross_tenant_http_edit_and_file_isolation(self):
        outsider = get_user_model().objects.create_user("outsider", password="OtherStrong!123")
        org = Organization.objects.create(name="Outro", trial_ends_at=month_after(timezone.now()))
        Membership.objects.create(organization=org, user=outsider, role="master")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(f"/products/{self.product.pk}/edit/").status_code, 404)
        job = Job.objects.create(
            organization=self.org,
            kind="report",
            status="done",
            requested_by=self.user,
            result_file="private.pdf",
        )
        self.assertEqual(self.client.get(f"/files/{job.pk}/").status_code, 404)

    def test_legacy_import_preserves_data_and_upgrades_password_hash(self):
        from pathlib import Path

        from legacy.estoquepro.domain import Inventory

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "legacy.sqlite3"
            legacy = Inventory(source)
            legacy.initialize("LegacyOnly!123", demo=True)
            output = io.StringIO()
            call_command("import_legacy", str(source), stdout=output)
            self.assertEqual(Product.objects.count(), 5)
            call_command("import_legacy", str(source), stdout=output)
            self.assertEqual(Product.objects.count(), 5)
            user = authenticate(username="admin", password="LegacyOnly!123")
            self.assertIsNotNone(user)
            self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
            self.assertEqual(legacy.dashboard()["units"], 94)

    def test_login_throttle_and_cannot_self_assign_creator(self):
        self.client.logout()
        for _ in range(20):
            self.assertEqual(
                self.client.post(
                    "/accounts/login/", {"username": "missing", "password": "bad"}
                ).status_code,
                200,
            )
        self.assertEqual(
            self.client.post(
                "/accounts/login/", {"username": "missing", "password": "bad"}
            ).status_code,
            429,
        )
        self.assertFalse(Creator.objects.exists())
        LoginThrottle.objects.update(window=timezone.now() - timedelta(minutes=6))
        self.assertEqual(
            self.client.post(
                "/accounts/login/",
                {"username": "master", "password": "StrongTestPass!123"},
            ).status_code,
            302,
        )

    def test_reorder_barcode_and_subscription_controls(self):
        self.product.barcode = "7891234567890"
        self.product.save()
        response = self.client.get("/barcode/", {"code": "7891234567890"})
        self.assertEqual(response.json()["id"], self.product.pk)
        order = reorder(self.a, self.product.pk, self.location.pk)
        self.assertEqual(order.lines.get().quantity, 3)
        self.assertEqual(self.client.get(f"/share/{order.pk}/").status_code, 200)
        self.org.renewal_enabled = True
        self.org.save()
        self.assertEqual(self.client.post("/subscription/").status_code, 302)
        self.org.refresh_from_db()
        self.assertFalse(self.org.renewal_enabled)
        self.assertTrue(self.client.get("/labels/").content.startswith(b"%PDF"))
        self.assertEqual(self.client.get("/report/pdf/?start=invalid").status_code, 400)

    def test_product_without_prerequisites_and_inline_registration(self):
        org = Organization.objects.create(name="Novo", trial_ends_at=month_after(timezone.now()))
        Membership.objects.create(organization=org, user=self.user, role="master")
        access = access_for(self.user, org.pk)
        p = save_product(access, dict(sku="SIMPLES", name="Sem pré-cadastros", price=0, minimum=0))
        self.assertEqual(p.category.name, "Geral")
        self.assertIsNone(p.supplier)
        another = save_product(access, dict(sku="OUTRO", name="Outro", price=0, minimum=0))
        self.assertEqual(p.category, another.category)
        p = save_product(
            self.a,
            dict(
                sku="INLINE",
                name="Inline",
                price=0,
                minimum=0,
                new_category="Categoria inline",
                new_supplier="Fornecedor inline",
            ),
        )
        self.assertEqual(p.category.name, "Categoria inline")
        self.assertEqual(p.supplier.name, "Fornecedor inline")
        session = self.client.session
        session["organization_id"] = org.pk
        session.save()
        response = self.client.post(
            "/new/products/",
            {
                "sku": "WEBMIN",
                "name": "Produto simples",
                "price": "0",
                "minimum": "0",
                "lead_days": "7",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Product.objects.filter(organization=org, sku="WEBMIN", category__name="Geral").exists()
        )

    def test_plans_preserve_context_and_creator_entitlement(self):
        owner = get_user_model().objects.create_user(
            "owner", password="SyntheticOwner!123", is_staff=True, is_superuser=True
        )
        Creator.objects.create(user=owner)
        self.client.force_login(owner)
        self.org.plan = "basic"
        self.org.save()
        response = self.client.get("/plans/")
        self.assertContains(response, "Criador · Completo")
        self.assertContains(response, "Completo ativo · Criador")
        self.assertNotContains(response, "Período encerrado")
        response = self.client.get("/subscription/")
        self.assertContains(response, "Completo — acesso permanente do Criador")
        self.assertNotContains(response, "Não contratado")
        self.assertNotContains(response, "Básico até:")
        self.assertNotContains(response, "Desativar renovação")
        self.assertContains(self.client.get("/"), "Configurações")
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get("/plans/"), "Completo ativo · Criador")

    def test_views_render_forms_and_lists(self):
        for kind in COLLECTION_KEYS:
            with self.subTest(kind=kind):
                self.assertEqual(self.client.get("/list/" + kind + "/").status_code, 200)
        for path in [
            "/move/",
            "/new/products/",
            "/new/lines/",
            "/team/new/",
            "/nfe/",
            "/transfer/",
            "/batch/",
            "/analysis/",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


COLLECTION_KEYS = [
    "products",
    "categories",
    "suppliers",
    "companies",
    "locations",
    "orders",
    "ledger",
    "quotes",
    "counts",
    "movements",
    "lots",
    "transfers",
    "audit",
    "jobs",
    "schedules",
    "members",
]
