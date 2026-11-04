"""Seleção e diagnóstico de Docker, sem modificar contextos ou privilégios."""

import os
import shutil
import subprocess
from pathlib import Path


class DockerUnavailable(RuntimeError):
    pass


def docker_runtime():
    if not shutil.which("docker"):
        raise DockerUnavailable(
            "Docker não está instalado ou não está no PATH. Instale o Docker para sua distribuição e inicie o serviço; depois execute python scripts/dev.py setup. A .venv já instalada pode ser preservada."
        )
    command = ["docker"]
    env = os.environ.copy()
    # Apenas o executor gerenciado exige selecionar explicitamente o daemon local.
    # Em PCs, preservar Docker Desktop, rootless e o contexto escolhido pelo usuário.
    if os.name != "nt" and Path("/etc/codex/network-policy.json").is_file():
        command.append("--host=unix:///var/run/docker.sock")
        for key in [
            "DOCKER_HOST",
            "DOCKER_CONTEXT",
            "DOCKER_TLS",
            "DOCKER_TLS_VERIFY",
            "DOCKER_CERT_PATH",
        ]:
            env.pop(key, None)
    try:
        result = subprocess.run(
            command + ["info", "--format", "{{.ServerVersion}}"],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise DockerUnavailable(
            "Não foi possível contatar o Docker. Inicie o Docker Desktop ou o serviço Docker e tente novamente."
        ) from None
    if result.returncode:
        if "permission denied" in result.stderr.lower():
            raise DockerUnavailable(
                "Seu usuário não tem acesso ao Docker. Ajuste o acesso ao serviço conforme sua distribuição e faça novo login. Não execute todo o projeto como root."
            )
        raise DockerUnavailable(
            "Docker instalado, mas o serviço/contexto não está acessível. Inicie o Docker e confirme que docker info funciona antes de repetir setup."
        )
    return command, env
