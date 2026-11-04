"""Backup integral local PostgreSQL. A saída binária nunca é impressa no terminal."""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from runtime import DockerUnavailable, docker_runtime

ROOT = Path(__file__).resolve().parents[1]
config = ROOT / "data/django-local.env"
if not config.exists():
    raise SystemExit("Execute scripts/dev.py setup primeiro.")
values = dict(
    line.split("=", 1)
    for line in config.read_text().splitlines()
    if line and not line.startswith("#")
)
try:
    docker, env = docker_runtime()
except DockerUnavailable as exc:
    raise SystemExit(str(exc))
folder = ROOT / "data/backups"
folder.mkdir(parents=True, exist_ok=True)
path = folder / (datetime.now(timezone.utc).strftime("django-%Y%m%dT%H%M%S%fZ") + ".dump")
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    with os.fdopen(fd, "wb") as stream:
        subprocess.run(
            docker
            + [
                "exec",
                "nerythstock-postgres",
                "pg_dump",
                "-U",
                values["PGUSER"],
                "-d",
                values["PGDATABASE"],
                "-Fc",
            ],
            stdout=stream,
            check=True,
            env=env,
        )
except Exception:
    path.unlink(missing_ok=True)
    raise
print("Backup PostgreSQL criado:", path.relative_to(ROOT))
