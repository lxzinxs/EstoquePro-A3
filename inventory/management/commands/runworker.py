import time

from django.core.management.base import BaseCommand

from inventory.jobs import claim, enqueue_due, perform


class Command(BaseCommand):
    help = "Worker PostgreSQL (SKIP LOCKED), com scheduler e retentativas; execute como serviço separado."

    def add_arguments(self, p):
        p.add_argument("--once", action="store_true")

    def handle(self, *args, **opts):
        while True:
            enqueue_due()
            task = claim()
            if task:
                pk, lease = task
                ok = perform(pk, lease)
                self.stdout.write(
                    f"Tarefa {pk}: " + ("concluída" if ok else "falhou/retentativa programada")
                )
            if opts["once"]:
                break
            if not task:
                time.sleep(2)
