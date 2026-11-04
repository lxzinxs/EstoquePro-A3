"""Backup integral local PostgreSQL. A saída binária nunca é impressa no terminal."""
import os
import subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
config=ROOT/'data/django-local.env'
if not config.exists():raise SystemExit('Execute scripts/dev.py setup primeiro.')
values=dict(line.split('=',1) for line in config.read_text().splitlines() if line and not line.startswith('#'))
env={k:v for k,v in os.environ.items() if k not in ['DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH']}
docker=['docker','--host=unix:///var/run/docker.sock'] if os.name!='nt' else ['docker']
folder=ROOT/'data/backups';folder.mkdir(parents=True,exist_ok=True)
path=folder/(datetime.now(timezone.utc).strftime('django-%Y%m%dT%H%M%S%fZ')+'.dump')
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
try:
    with os.fdopen(fd,'wb') as stream:
        subprocess.run(docker+['exec','nerythstock-postgres','pg_dump','-U',values['PGUSER'],'-d',values['PGDATABASE'],'-Fc'],stdout=stream,check=True,env=env)
except Exception:
    path.unlink(missing_ok=True);raise
print('Backup PostgreSQL criado:',path.relative_to(ROOT))
