import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from ..forms import ScopedModelForm
from ..jobs import claim, enqueue_due, perform
from ..models import (
    Category,
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
)
from ..services import (
    access_for,
    add_member,
    analytics,
    confirm_transfer,
    create_transfer,
    move,
    quantity,
    reorder,
    save_product,
)
from .test_core import InventoryFixture


class ReviewTests(InventoryFixture, TransactionTestCase):
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

    def test_member_cannot_read_cash_analysis_but_can_export_stock(self):
        member = add_member(
            self.a,
            "review.member",
            "review@example.test",
            "ReviewPassword!123",
            "member",
        )
        Ledger.objects.create(
            organization=self.org,
            kind="receivable",
            description="Privado",
            amount=999,
            due_date=timezone.localdate(),
        )
        self.client.force_login(member)
        self.assertEqual(self.client.get("/analysis/").status_code, 403)
        self.assertEqual(self.client.get("/report/csv/").status_code, 200)
        with self.assertRaises(PermissionDenied):
            analytics(access_for(member, self.org.pk))

    def test_invalid_query_values_do_not_crash(self):
        for value in ["abc", "-1", "9" * 100]:
            self.assertEqual(
                self.client.get("/list/movements/", {"product": value}).status_code, 400
            )
            self.assertEqual(self.client.post("/switch/", {"organization": value}).status_code, 403)
        self.assertEqual(self.client.get("/notifications/", {"since": "9" * 100}).status_code, 200)
        self.assertEqual(self.client.post("/reorder/1/", {"location": "invalid"}).status_code, 302)

    def test_inactive_actor_with_stale_access_is_blocked(self):
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.entry()
        with self.assertRaises(PermissionDenied):
            access_for(self.user, self.org.pk)

    def test_stock_limit_rolls_back_without_partial_update(self):
        self.entry(999999999, "1")
        with self.assertRaises(ValidationError):
            self.entry(1, "2", code="EXCESSO")
        self.assertEqual(quantity(self.product), 999999999)
        self.assertEqual(Movement.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.average_cost, 1)

    def test_notes_cannot_disguise_sales_as_transfers(self):
        self.entry(10, "10")
        move(
            self.a,
            self.product.pk,
            self.location.pk,
            "exit",
            2,
            "Transferência falsa no motivo",
        )
        self.assertEqual(analytics(self.a)["consumed"], Decimal("20"))
        destination = Location.objects.create(
            organization=self.org, company=self.company, name="Destino"
        )
        create_transfer(self.a, self.product.pk, self.location.pk, destination.pk, 2)
        self.assertEqual(analytics(self.a)["consumed"], Decimal("20"))

    def test_long_lot_codes_do_not_collide_on_transfer(self):
        self.entry(
            2,
            "10",
            code="A" * 79 + "1",
            expiry=timezone.localdate() + timedelta(days=1),
        )
        self.entry(
            2,
            "10",
            code="A" * 79 + "2",
            expiry=timezone.localdate() + timedelta(days=2),
        )
        destination = Location.objects.create(
            organization=self.org, company=self.company, name="Destino"
        )
        transfer = create_transfer(self.a, self.product.pk, self.location.pk, destination.pk, 4)
        confirm_transfer(self.a, transfer.pk)
        self.assertEqual(Lot.objects.filter(location=destination).count(), 2)
        self.assertEqual(quantity(self.product, destination), 4)

    def test_child_master_cannot_disable_parent_renewal_as_parent_member(self):
        child = Organization.objects.create(
            name="Filha",
            plan="complete",
            trial_ends_at=self.org.trial_ends_at,
            billing_parent=self.org,
        )
        Membership.objects.create(organization=child, user=self.user, role="master")
        Membership.objects.filter(organization=self.org, user=self.user).update(role="member")
        self.org.renewal_enabled = True
        self.org.save()
        session = self.client.session
        session["organization_id"] = child.pk
        session.save()
        self.assertEqual(self.client.post("/subscription/").status_code, 403)
        self.org.refresh_from_db()
        self.assertTrue(self.org.renewal_enabled)

    def test_parent_downgrade_blocks_child_writes_but_preserves_reads(self):
        child = Organization.objects.create(
            name="Filha",
            plan="complete",
            trial_ends_at=self.org.trial_ends_at,
            billing_parent=self.org,
        )
        Membership.objects.create(organization=child, user=self.user, role="master")
        self.org.plan = "basic"
        self.org.save()
        access = access_for(self.user, child.pk)
        with self.assertRaises(PermissionDenied):
            save_product(access, dict(sku="BYPASS", name="Bypass", price=0, minimum=0))
        session = self.client.session
        session["organization_id"] = child.pk
        session.save()
        self.assertEqual(self.client.get("/report/csv/").status_code, 200)

    def test_circular_subscription_is_rejected(self):
        self.org.billing_parent = self.org
        with self.assertRaises(ValidationError):
            self.org.full_clean()

    def test_received_order_cannot_gain_line_after_form_validation(self):
        order = PurchaseOrder.objects.create(
            organization=self.org, supplier=self.supplier, location=self.location
        )
        PurchaseLine.objects.create(order=order, product=self.product, quantity=1, unit_cost=10)
        original = ScopedModelForm.clean

        def receive_after_clean(form):
            result = original(form)
            if form._meta.model is PurchaseLine:
                from ..services import receive_order

                receive_order(self.a, order.pk)
            return result

        with patch.object(ScopedModelForm, "clean", receive_after_clean):
            response = self.client.post(
                "/new/lines/",
                {
                    "order": order.pk,
                    "product": self.product.pk,
                    "quantity": 5,
                    "unit_cost": "10",
                    "lot_code": "NOVO",
                    "expiry": "",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pedido já recebido.")
        self.assertEqual(order.lines.count(), 1)
        self.assertEqual(quantity(self.product), 1)

    def test_worker_lease_blocks_late_worker_and_duplicate_execution(self):
        job = Job.objects.create(
            organization=self.org,
            kind="report",
            requested_by=self.user,
            payload={"format": "pdf"},
        )
        old = claim()
        Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=31))
        enqueue_due()
        new = claim()
        self.assertNotEqual(old[1], new[1])
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(PRIVATE_ROOT=Path(directory)),
        ):
            self.assertFalse(perform(*old))
            self.assertTrue(perform(*new))
            self.assertFalse(perform(*new))
            self.assertEqual(len(list(Path(directory).rglob("*.pdf"))), 1)
            job.refresh_from_db()
            self.assertEqual(job.status, "done")

    def test_worker_timeout_and_failure_attempts_are_bounded(self):
        job = Job.objects.create(
            organization=self.org,
            kind="report",
            requested_by=self.user,
            status="running",
            attempts=3,
            started_at=timezone.now() - timedelta(minutes=31),
        )
        enqueue_due()
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertIsNone(claim())
        job = Job.objects.create(
            organization=self.org,
            kind="report",
            requested_by=self.user,
            payload={"format": "invalid"},
        )
        with patch("inventory.jobs.logging.getLogger"):
            for attempt in range(3):
                claimed = claim()
                self.assertFalse(perform(*claimed))
                Job.objects.filter(pk=job.pk).update(
                    available_at=timezone.now() - timedelta(seconds=1)
                )
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.attempts, 3)

    def test_archived_product_reorder_is_validation_error(self):
        self.product.active = False
        self.product.save()
        with self.assertRaises(ValidationError):
            reorder(self.a, self.product.pk, self.location.pk)

    def test_dashboard_listing_and_analysis_do_not_grow_queries_per_product(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        paths = ["/", "/list/products/", "/analysis/"]
        baseline = {}
        for path in paths:
            with CaptureQueriesContext(connection) as captured:
                self.assertEqual(self.client.get(path).status_code, 200)
            baseline[path] = len(captured)
        Product.objects.bulk_create(
            [
                Product(
                    organization=self.org,
                    category=self.category,
                    sku=f"PERF-{i}",
                    name=f"Produto {i}",
                )
                for i in range(100)
            ]
        )
        for path in paths:
            with self.subTest(path=path), CaptureQueriesContext(connection) as captured:
                self.assertEqual(self.client.get(path).status_code, 200)
            self.assertLessEqual(len(captured), baseline[path] + 3)

    def test_cross_tenant_batch_rollback_and_invalid_xml_rollback(self):
        self.entry(5)
        other = Organization.objects.create(name="Outro", trial_ends_at=self.org.trial_ends_at)
        foreign_category = Category.objects.create(organization=other, name="Outro")
        foreign = Product.objects.create(
            organization=other, category=foreign_category, sku="X", name="Privado"
        )
        from ..services import batch_move

        lines = [
            dict(
                product_id=self.product.pk,
                location_id=self.location.pk,
                kind="exit",
                qty=1,
                note="Primeiro",
            ),
            dict(
                product_id=foreign.pk,
                location_id=self.location.pk,
                kind="exit",
                qty=1,
                note="Segundo",
            ),
        ]
        with self.assertRaises(ValidationError):
            batch_move(self.a, lines)
        self.assertEqual(quantity(self.product), 5)
        from ..integrations import import_nfe

        xml = (
            '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe'
            + ("7" * 44)
            + '"><ide><nNF>50</nNF></ide><det><prod><cProd>A1</cProd><qCom>1</qCom><vUnCom>10</vUnCom></prod></det><det><prod><cProd>MISSING</cProd><qCom>1</qCom><vUnCom>10</vUnCom></prod></det><total><ICMSTot><vNF>20</vNF></ICMSTot></total></infNFe></NFe></nfeProc>'
        ).encode()
        with self.assertRaises(ValidationError):
            import_nfe(self.a, xml, self.location.pk)
        self.assertEqual(quantity(self.product), 5)
        self.assertEqual(Movement.objects.count(), 1)

    def test_quota_and_claim_are_safe_under_concurrency(self):
        self.org.plan = "basic"
        self.org.save()
        Product.objects.bulk_create(
            [
                Product(
                    organization=self.org, category=self.category, sku=f"LIMIT-{i}", name="Limite"
                )
                for i in range(48)
            ]
        )
        uid, oid = self.user.pk, self.org.pk

        def create_one(index):
            connections.close_all()
            try:
                access = access_for(get_user_model().objects.get(pk=uid), oid)
                save_product(
                    access, dict(sku=f"RACE-{index}", name="Concorrência", price=0, minimum=0)
                )
                return True
            except ValidationError:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create_one, range(2)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(Product.objects.filter(organization=self.org, active=True).count(), 50)
        jobs = [
            Job.objects.create(organization=self.org, kind="backup", requested_by=self.user)
            for _ in range(2)
        ]

        def take_one(_):
            connections.close_all()
            try:
                return claim()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            claimed = list(executor.map(take_one, range(2)))
        self.assertEqual({item[0] for item in claimed}, {job.pk for job in jobs})

    def test_invalid_forms_xss_and_private_file_traversal(self):
        response = self.client.post("/new/products/", {})
        self.assertContains(response, "Este campo é obrigatório")
        save_product(self.a, dict(sku="XSS", name="<script>alert(1)</script>", price=0, minimum=0))
        response = self.client.get("/list/products/")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        job = Job.objects.create(
            organization=self.org,
            kind="report",
            requested_by=self.user,
            status="done",
            result_file="../django-local.env",
        )
        self.assertEqual(self.client.get(f"/files/{job.pk}/").status_code, 404)
        self.assertEqual(
            self.client.get("/list/movements/", {"product": "1 OR 1=1"}).status_code, 400
        )

    def test_brand_upload_reencodes_image_and_rejects_svg(self):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        image = io.BytesIO()
        Image.new("RGB", (4, 4), "blue").save(image, "PNG")
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(PRIVATE_ROOT=Path(directory)),
        ):
            response = self.client.post(
                "/brand/",
                {
                    "logo": SimpleUploadedFile(
                        "mark.png", image.getvalue(), content_type="image/png"
                    )
                },
            )
            self.assertEqual(response.status_code, 302)
            self.org.refresh_from_db()
            saved = self.org.logo_file
            self.assertTrue((Path(directory) / saved).is_file())
            response = self.client.post(
                "/brand/",
                {
                    "logo": SimpleUploadedFile(
                        "mark.svg",
                        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                        content_type="image/svg+xml",
                    )
                },
            )
            self.assertEqual(response.status_code, 200)
            self.org.refresh_from_db()
            self.assertEqual(self.org.logo_file, saved)

    def test_reorder_level_one_and_zero_can_be_edited_without_changing_stock(self):
        self.entry(2)
        response = self.client.post(f"/products/{self.product.pk}/alert/", {"minimum": "1"})
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.minimum, 1)
        self.assertFalse(self.client.get("/").context["rows"][0]["low"])
        move(self.a, self.product.pk, self.location.pk, "exit", 1, "Consumo")
        self.assertTrue(self.client.get("/").context["rows"][0]["low"])
        self.client.post(f"/products/{self.product.pk}/alert/", {"minimum": "0"})
        self.assertFalse(self.client.get("/").context["rows"][0]["low"])
        self.assertEqual(quantity(self.product), 1)
        self.assertEqual(
            self.client.post(f"/products/{self.product.pk}/alert/", {"minimum": "-1"}).status_code,
            200,
        )

    def test_admin_adds_members_but_only_master_assigns_management_roles(self):
        from ..services import change_member

        admin = add_member(self.a, "admin.review", "admin@example.test", "StrongAdmin!123", "admin")
        access = access_for(admin, self.org.pk)
        regular = add_member(
            access, "staff.review", "staff@example.test", "StrongStaff!123", "member"
        )
        self.assertEqual(Membership.objects.get(user=regular).role, "member")
        for role in ("admin", "master", "creator"):
            with self.assertRaises(PermissionDenied):
                add_member(
                    access, "forged." + role, "forged@example.test", "StrongForged!123", role
                )
        self.client.force_login(admin)
        self.assertEqual(self.client.get("/team/new/").status_code, 200)
        self.assertEqual(self.client.get("/list/members/").status_code, 200)
        self.assertContains(self.client.get("/"), "Adicionar membro")
        response = self.client.post(
            "/team/new/",
            {
                "username": "forged.web",
                "email": "web@example.test",
                "password": "StrongWeb!123",
                "role": "master",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="forged.web").exists())
        membership = Membership.objects.get(user=regular)
        self.assertEqual(
            self.client.post(f"/team/{membership.pk}/", {"role": "master"}).status_code, 403
        )
        change_member(self.a, membership.pk, "admin")
        membership.refresh_from_db()
        self.assertEqual(membership.role, "admin")
        self.client.force_login(regular)
        self.assertEqual(
            self.client.post(f"/products/{self.product.pk}/alert/", {"minimum": "1"}).status_code,
            302,
        )

    def test_member_cannot_change_reorder_level(self):
        member = add_member(
            self.a, "threshold.member", "t@example.test", "ThresholdStrong!123", "member"
        )
        self.client.force_login(member)
        self.assertEqual(
            self.client.post(f"/products/{self.product.pk}/alert/", {"minimum": "1"}).status_code,
            403,
        )

    def test_creator_provision_is_exclusive_and_never_prints_password(self):
        import io

        from django.core.management import call_command
        from django.core.management.base import CommandError

        from ..models import Creator

        output = io.StringIO()
        with patch(
            "inventory.management.commands.provision_creator.getpass.getpass",
            side_effect=["SyntheticCreator!123", "SyntheticCreator!123"],
        ):
            call_command("provision_creator", username="review.owner", stdout=output)
        creator = Creator.objects.get().user
        self.assertTrue(creator.check_password("SyntheticCreator!123"))
        self.assertTrue(creator.is_superuser and creator.is_staff)
        self.assertNotIn("SyntheticCreator!123", output.getvalue())
        with patch("inventory.management.commands.provision_creator.getpass.getpass") as prompt:
            with self.assertRaises(CommandError):
                call_command("provision_creator", username="another.owner", stdout=output)
            prompt.assert_not_called()
        with patch(
            "inventory.management.commands.provision_creator.getpass.getpass",
            side_effect=["DifferentStrong!123", "MismatchStrong!123"],
        ):
            with self.assertRaises(CommandError):
                call_command("provision_creator", username="review.owner", stdout=output)
        creator.refresh_from_db()
        self.assertTrue(creator.check_password("SyntheticCreator!123"))

    def test_worker_command_executes_real_task_once(self):
        import io

        from django.core.management import call_command

        job = Job.objects.create(organization=self.org, kind="backup", requested_by=self.user)
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(PRIVATE_ROOT=Path(directory)),
        ):
            output = io.StringIO()
            call_command("runworker", once=True, stdout=output)
            job.refresh_from_db()
            self.assertEqual(job.status, "done")
            self.assertIn("concluída", output.getvalue())
            self.assertTrue((Path(directory) / job.result_file).is_file())

    def test_http_purchase_payment_transfer_and_queue_flow(self):
        import json

        self.assertEqual(
            self.client.post(
                "/new/orders/", {"supplier": self.supplier.pk, "location": self.location.pk}
            ).status_code,
            302,
        )
        order = PurchaseOrder.objects.get()
        self.assertEqual(
            self.client.post(
                "/new/lines/",
                {
                    "order": order.pk,
                    "product": self.product.pk,
                    "quantity": 4,
                    "unit_cost": "10",
                    "lot_code": "HTTP",
                    "expiry": "",
                },
            ).status_code,
            302,
        )
        self.assertEqual(self.client.post(f"/action/receive/{order.pk}/").status_code, 302)
        self.assertEqual(quantity(self.product), 4)
        ledger = Ledger.objects.get()
        self.assertEqual(
            self.client.post(
                f"/payment/{ledger.pk}/", {"value": "10", "date": str(timezone.localdate())}
            ).status_code,
            302,
        )
        self.assertEqual(ledger.payments.get().amount, Decimal("10"))
        destination = Location.objects.create(
            organization=self.org, company=self.company, name="HTTP destino"
        )
        self.assertEqual(
            self.client.post(
                "/transfer/",
                {
                    "product": self.product.pk,
                    "source": self.location.pk,
                    "destination": destination.pk,
                    "quantity": 1,
                },
            ).status_code,
            302,
        )
        from ..models import Transfer

        transfer = Transfer.objects.get()
        self.assertEqual(self.client.post(f"/action/confirm/{transfer.pk}/").status_code, 302)
        self.assertEqual(quantity(self.product, destination), 1)
        self.assertEqual(
            self.client.post(
                "/batch/",
                {
                    "lines": json.dumps(
                        [
                            dict(
                                product_id=self.product.pk,
                                location_id=self.location.pk,
                                kind="exit",
                                qty=1,
                                note="HTTP lote",
                            )
                        ]
                    )
                },
            ).status_code,
            302,
        )
        self.assertEqual(quantity(self.product), 3)
        self.assertEqual(self.client.post("/queue/report/").status_code, 302)
        self.assertEqual(Job.objects.get().kind, "report")

    def test_xml_lots_due_dates_and_no_external_email_configuration(self):
        from ..integrations import import_nfe
        from ..models import Invoice

        xml = (
            '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe'
            + ("8" * 44)
            + '"><ide><nNF>80</nNF></ide><det><prod><cProd>A1</cProd><qCom>3</qCom><vUnCom>10</vUnCom><rastro><nLote>NFE-L1</nLote><qLote>3</qLote><dVal>2030-12-01</dVal></rastro></prod></det><total><ICMSTot><vNF>30</vNF></ICMSTot></total><cobr><dup><dVenc>2030-12-01</dVenc><vDup>10</vDup></dup><dup><dVenc>2030-12-10</dVenc><vDup>20</vDup></dup></cobr></infNFe></NFe></nfeProc>'
        ).encode()
        import_nfe(self.a, xml, self.location.pk)
        self.assertEqual(Ledger.objects.count(), 2)
        self.assertEqual(Lot.objects.get().code, "NFE-L1")
        self.assertEqual(Invoice.objects.count(), 1)
        self.client.logout()
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST=""
        ):
            response = self.client.post(
                "/accounts/password_reset/", {"email": "master@example.test"}
            )
            self.assertContains(response, "ainda não configurada")

    def test_inactive_master_does_not_allow_removing_last_active_master(self):
        from ..services import change_member

        inactive = add_member(
            self.a, "inactive.master", "inactive@example.test", "InactiveStrong!123", "master"
        )
        get_user_model().objects.filter(pk=inactive.pk).update(is_active=False)
        own = Membership.objects.get(user=self.user, organization=self.org)
        with self.assertRaises(ValidationError):
            change_member(self.a, own.pk, remove=True)
        other = Membership.objects.get(user=inactive, organization=self.org)
        change_member(self.a, other.pk, remove=True)
        self.assertTrue(Membership.objects.filter(pk=own.pk).exists())
