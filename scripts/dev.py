"""Ambiente local: PostgreSQL isolado e configuração fora do Git. Bash/fish/PowerShell."""
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from runtime import docker_runtime,DockerUnavailable
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
folder=ROOT/'data';folder.mkdir(exist_ok=True)
config=folder/'django-local.env'
if not config.exists():
    with config.open('x') as f:
        f.write('DJANGO_DEBUG=1\nPGDATABASE=nerythstock\nPGUSER=nerythstock\nPGPASSWORD='+secrets.token_urlsafe(32)+'\nPGHOST=127.0.0.1\nPGPORT=55432\n')
    config.chmod(0o600)
values=dict(line.split('=',1) for line in config.read_text().splitlines() if line and not line.startswith('#'))
env={**os.environ,**values}
env['DJANGO_SETTINGS_MODULE']='config.settings'
python=ROOT/('.venv/Scripts/python.exe' if os.name=='nt' else '.venv/bin/python')
if not python.exists():sys.exit('Crie .venv e instale requirements.txt primeiro.')
if len(sys.argv)>1 and sys.argv[1]=='setup':
    try:docker,docker_env=docker_runtime()
    except DockerUnavailable as exc:sys.exit(str(exc))
    pgfile=folder/'postgres-local.env'
    pgfile.write_text('POSTGRES_DB='+values['PGDATABASE']+'\nPOSTGRES_USER='+values['PGUSER']+'\nPOSTGRES_PASSWORD='+values['PGPASSWORD']+'\n');pgfile.chmod(0o600)
    inspect=subprocess.run(docker+['inspect','--format','{{.State.Running}}','nerythstock-postgres'],capture_output=True,env=docker_env,text=True)
    if inspect.returncode:
        subprocess.run(docker+['run','-d','--name','nerythstock-postgres','--env-file',str(pgfile),'-p','127.0.0.1:55432:5432','-v','nerythstock-postgres-data:/var/lib/postgresql/data','postgres:17-bookworm'],check=True,env=docker_env)
    elif inspect.stdout.strip()!='true':subprocess.run(docker+['start','nerythstock-postgres'],check=True,env=docker_env)
    for _ in range(60):
        r=subprocess.run(docker+['exec','nerythstock-postgres','pg_isready','-U',values['PGUSER'],'-d',values['PGDATABASE']],env=docker_env,capture_output=True)
        if r.returncode==0:break
        time.sleep(.5)
    else:sys.exit('PostgreSQL não ficou pronto; examine docker logs nerythstock-postgres.')
    args=['migrate']
else:args=sys.argv[1:] or ['runserver','127.0.0.1:8000','--noreload']
if args[0] in ('provision_creator','runserver','runworker','import_legacy','migrate','test','shell') and '--help' not in args:
    probe=subprocess.run([str(python),'-c',"import psycopg; c=psycopg.connect(connect_timeout=3); c.close()"],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if probe.returncode:
        sys.exit('PostgreSQL não está acessível. Execute python scripts/dev.py setup e só prossiga após as migrações terminarem. Não apague data/ ou o volume do banco.')
raise SystemExit(subprocess.call([str(python),'manage.py',*args],env=env))
