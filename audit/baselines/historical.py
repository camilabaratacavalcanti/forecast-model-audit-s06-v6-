"""
Stage 4C — execução histórica (classe H) num clone temporário fixado no commit de fechamento.

`checkout(commit, destino)` faz `git clone --shared --no-checkout` do repositório e `checkout` do commit:
o harness histórico roda SEM alteração, com o código, os dados e a evidência daquele commit, e nunca
lê o HEAD. O repositório de trabalho não é tocado (o clone compartilha só os objetos).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def git(*args, cwd=REPO) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def checkout(commit: str, destination: Path) -> Path:
    destination = Path(destination)
    full = git("rev-parse", "--verify", f"{commit}^{{commit}}").strip()
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(REPO), str(destination)], check=True,
                   capture_output=True)
    subprocess.run(["git", "checkout", "-q", full], cwd=destination, check=True, capture_output=True)
    if git("rev-parse", "HEAD", cwd=destination).strip() != full:
        raise RuntimeError(f"clone histórico não está em {full}")
    return destination


def clean_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHASHSEED")}
    env.update(extra)
    return env


def run(root: Path, *args, isolated: bool = False, env: dict | None = None) -> subprocess.CompletedProcess:
    """Executa `python [-I] <args>` dentro do clone (cwd = clone)."""
    command = [sys.executable, *(["-I"] if isolated else []), *map(str, args)]
    return subprocess.run(command, cwd=root, capture_output=True, text=True, env=env or clean_env())
