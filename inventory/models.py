from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=120)
    plan = models.CharField(
        max_length=12,
        choices=[("basic", "Básico"), ("complete", "Completo")],
        default="basic",
    )
    trial_ends_at = models.DateTimeField()
    paid_until = models.DateTimeField(null=True, blank=True)
    renewal_enabled = models.BooleanField(default=False)
    logo_file = models.CharField(max_length=180, blank=True)
    billing_parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="businesses",
    )
    logo_url = models.URLField(blank=True, help_text="URL HTTPS da marca; sem download no servidor")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def billing_account(self):
        account = self
        visited = set()
        while account.billing_parent_id:
            if account.pk in visited:
                raise ValidationError("Vínculo circular de assinatura.")
            visited.add(account.pk)
            account = account.billing_parent
        return account

    def clean(self):
        super().clean()
        if self.billing_parent_id:
            account = self.billing_account
            if account.pk == self.pk:
                raise ValidationError("Vínculo circular de assinatura.")

    @property
    def writable(self):
        account = self.billing_account
        return (account.plan == "basic" and account.trial_ends_at > timezone.now()) or (
            account.plan == "complete"
            and account.paid_until is not None
            and account.paid_until > timezone.now()
        )


class Membership(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    role = models.CharField(
        max_length=10,
        choices=[("member", "Membro"), ("admin", "Admin"), ("master", "Master")],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="unique_membership")
        ]


class Scoped(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)

    class Meta:
        abstract = True


class Company(Scoped):
    name = models.CharField(max_length=120)

    def __str__(self):
        return self.name


class Location(Scoped):
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    kind = models.CharField(
        max_length=10,
        choices=[("stock", "Estoque"), ("service", "Atendimento")],
        default="stock",
    )

    def __str__(self):
        return f"{self.company.name} / {self.name}"


class Category(Scoped):
    name = models.CharField(max_length=80)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="category_name_org")
        ]

    def __str__(self):
        return self.name


class Supplier(Scoped):
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.name


class Product(Scoped):
    sku = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, null=True, blank=True)
    barcode = models.CharField(max_length=64, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    average_cost = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    minimum = models.PositiveIntegerField(default=0)
    lead_days = models.PositiveIntegerField(default=7)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "sku"], name="sku_org"),
            models.UniqueConstraint(
                fields=["organization", "barcode"],
                condition=~Q(barcode=""),
                name="barcode_org",
            ),
            models.CheckConstraint(
                condition=Q(price__gte=0) & Q(average_cost__gte=0),
                name="product_money_positive",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"


class Lot(Scoped):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    code = models.CharField(max_length=80)
    expiry = models.DateField(null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "location", "code"], name="lot_key")
        ]


class Movement(Scoped):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=10, choices=[("entry", "Entrada"), ("exit", "Saída")])
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    note = models.CharField(max_length=240)
    purpose = models.CharField(
        max_length=10,
        choices=[
            ("stock", "Estoque"),
            ("transfer", "Transferência"),
            ("count", "Inventário"),
            ("legacy", "Legado"),
        ],
        default="stock",
    )
    allocations = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0) & Q(unit_cost__gte=0),
                name="movement_positive",
            )
        ]


class PurchaseOrder(Scoped):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=12,
        default="pending",
        choices=[("pending", "Pendente"), ("received", "Recebido")],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Pedido #{self.pk} / {self.supplier}"


class PurchaseLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)
    lot_code = models.CharField(max_length=80, default="PADRAO")
    expiry = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0) & Q(unit_cost__gte=0),
                name="purchase_positive",
            )
        ]


class Transfer(Scoped):
    source = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="+")
    destination = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="+")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    allocations = models.JSONField(default=list)
    status = models.CharField(max_length=10, default="pending")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0) & ~Q(source=models.F("destination")),
                name="transfer_valid",
            )
        ]


class Ledger(Scoped):
    kind = models.CharField(
        max_length=10, choices=[("payable", "A pagar"), ("receivable", "A receber")]
    )
    description = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField()
    source_key = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ledger_positive"),
            models.UniqueConstraint(
                fields=["organization", "source_key"],
                condition=~Q(source_key=""),
                name="ledger_source_unique",
            ),
        ]


class Payment(models.Model):
    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="payment_positive")]


class Invoice(Scoped):
    key = models.CharField(max_length=44)
    number = models.CharField(max_length=20)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "key"], name="invoice_key_org")
        ]


class Quote(Scoped):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    round_key = models.CharField(max_length=40)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "product", "round_key", "supplier"],
                name="quote_supplier_round",
            ),
            models.CheckConstraint(condition=Q(price__gte=0), name="quote_positive"),
        ]


class StockCount(Scoped):
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT)
    counted = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    status = models.CharField(max_length=10, default="pending")


class Audit(Scoped):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    action = models.CharField(max_length=80)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class Job(Scoped):
    kind = models.CharField(
        max_length=20,
        choices=[("report", "Relatório"), ("backup", "Backup"), ("briefing", "Resumo")],
    )
    lease = models.UUIDField(null=True, editable=False)
    status = models.CharField(max_length=12, default="pending")
    payload = models.JSONField(default=dict)
    result_file = models.CharField(max_length=180, blank=True)
    error = models.CharField(max_length=200, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)


class Schedule(Scoped):
    kind = models.CharField(max_length=20, choices=Job._meta.get_field("kind").choices)
    interval_hours = models.PositiveIntegerField(default=24)
    next_run = models.DateTimeField(default=timezone.now)
    enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "kind"], name="schedule_org_kind")
        ]


class Creator(models.Model):
    """Um único dono global; provisionado só por comando administrativo local."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name="one_creator_slot")]


class LegacyImport(models.Model):
    digest = models.CharField(max_length=64, unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class LoginThrottle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    window = models.DateTimeField(default=timezone.now)
