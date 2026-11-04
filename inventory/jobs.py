import json
import logging
import os
import tempfile
import uuid
from datetime import timedelta

from django.conf import settings
from django.core import serializers
from django.db import transaction
from django.utils import timezone

from .models import (
    Audit,
    Category,
    Company,
    Invoice,
    Job,
    Ledger,
    Location,
    Lot,
    Membership,
    Movement,
    Organization,
    Payment,
    Product,
    PurchaseLine,
    PurchaseOrder,
    Quote,
    Schedule,
    StockCount,
    Supplier,
    Transfer,
)
from .reports import export
from .services import access_for, analytics, permit


@transaction.atomic
def enqueue_due():
    stale = Job.objects.filter(
        status="running", started_at__lt=timezone.now() - timedelta(minutes=30)
    )
    stale.filter(attempts__gte=3).update(
        status="failed",
        lease=None,
        finished_at=timezone.now(),
        error="Limite de tentativas atingido após timeout.",
    )
    stale.filter(attempts__lt=3).update(
        status="pending",
        lease=None,
        available_at=timezone.now(),
        error="Tarefa recuperada após timeout do worker.",
    )
    for schedule in Schedule.objects.select_for_update(skip_locked=True).filter(
        enabled=True, next_run__lte=timezone.now()
    ):
        master = Membership.objects.filter(
            organization=schedule.organization, role="master", user__is_active=True
        ).first()
        if master:
            Job.objects.create(
                organization=schedule.organization,
                kind=schedule.kind,
                requested_by=master.user,
                payload={"format": "pdf"},
            )
        schedule.next_run = timezone.now() + timedelta(hours=max(1, schedule.interval_hours))
        schedule.save(update_fields=["next_run"])


@transaction.atomic
def claim():
    job = (
        Job.objects.select_for_update(skip_locked=True)
        .filter(status="pending", attempts__lt=3, available_at__lte=timezone.now())
        .order_by("pk")
        .first()
    )
    if not job:
        return None
    job.lease = uuid.uuid4()
    job.status = "running"
    job.started_at = timezone.now()
    job.attempts += 1
    job.error = ""
    job.save()
    return job.pk, job.lease


def perform(pk, lease):
    job = (
        Job.objects.select_related("organization", "requested_by")
        .filter(pk=pk, status="running", lease=lease)
        .first()
    )
    if not job:
        return False
    try:
        a = access_for(job.requested_by, job.organization_id)
        permit(
            a,
            "master" if job.kind == "backup" else "admin",
            write=False,
            premium=job.kind != "backup",
        )
        if job.kind == "report":
            data, _ = export(a, job.payload.get("format", "pdf"))
            suffix = job.payload.get("format", "pdf")
        elif job.kind == "briefing":
            result = analytics(a)
            data = json.dumps(result, default=str, ensure_ascii=False, indent=2).encode()
            suffix = "json"
        elif job.kind == "backup":
            # Snapshot consistente, incluindo relacionamentos, sem hashes, sessões ou credenciais.
            from django.db import connection

            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                grouped = {}
                for model in [
                    Organization,
                    Company,
                    Location,
                    Category,
                    Supplier,
                    Product,
                    Lot,
                    Movement,
                    PurchaseOrder,
                    Transfer,
                    Ledger,
                    Invoice,
                    Quote,
                    StockCount,
                    Audit,
                ]:
                    query = (
                        model.objects.filter(pk=a.organization.pk)
                        if model == Organization
                        else model.objects.filter(organization=a.organization)
                    )
                    grouped[model._meta.label] = json.loads(serializers.serialize("json", query))
                grouped["inventory.PurchaseLine"] = json.loads(
                    serializers.serialize(
                        "json",
                        PurchaseLine.objects.filter(order__organization=a.organization),
                    )
                )
                grouped["inventory.Payment"] = json.loads(
                    serializers.serialize(
                        "json",
                        Payment.objects.filter(ledger__organization=a.organization),
                    )
                )
                grouped["format"] = "estoquepro-tenant-export-v1"
                grouped["notice"] = (
                    "Exportação de dados de negócio. Restauração integral do servidor exige também pg_dump e armazenamento de arquivos."
                )
                data = json.dumps(grouped, ensure_ascii=False, indent=2).encode()
                suffix = "json"
        else:
            raise ValueError("Tarefa desconhecida")
        root = settings.PRIVATE_ROOT
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = f"{job.organization_id}/{job.pk}-{uuid.uuid4().hex}.{suffix}"
        path = root / name
        path.parent.mkdir(exist_ok=True, mode=0o700)
        fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".job-")
        from pathlib import Path

        temporary = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        changed = Job.objects.filter(pk=pk, status="running", lease=lease).update(
            status="done",
            lease=None,
            result_file=name,
            finished_at=timezone.now(),
            error="",
        )
        if not changed:
            path.unlink(missing_ok=True)
            return False
    except (
        Exception
    ):  # O worker deve sobreviver a falhas de arquivo/banco sem registrar dados privados.
        logging.getLogger(__name__).error("Falha na tarefa id=%s tipo=%s", pk, job.kind)
        retry = job.attempts < 3
        Job.objects.filter(pk=pk, status="running", lease=lease).update(
            lease=None,
            status="pending" if retry else "failed",
            available_at=timezone.now() + timedelta(seconds=30 * job.attempts),
            error="Falha na tarefa; confira permissões, assinatura e configuração.",
            finished_at=None if retry else timezone.now(),
        )
        return False
    return True
