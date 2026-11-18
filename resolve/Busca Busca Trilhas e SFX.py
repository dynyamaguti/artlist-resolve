#!/usr/bin/env python3
"""DaVinci Resolve → Workspace ▸ Scripts ▸ Busca Busca Trilhas e SFX

Abre o dashboard de busca do Artlist. Se o servidor local ainda não estiver rodando, sobe em segundo plano.
Instalado em: ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/
"""
import os
import subprocess
import time
import urllib.request
from pathlib import Path

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"
BASE = Path.home() / "Library/Application Support/ArtlistResolve"
APP = BASE / "app"
LOG = BASE / "server.log"
PYTHONS = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]


def up():
    try:
        urllib.request.urlopen(URL + "/api/ping", timeout=2).read()
        return True
    except Exception:
        return False


def start_server():
    py = next((p for p in PYTHONS if os.path.exists(p)), None)
    if not py or not (APP / "server.py").exists():
        print("Artlist: instalação não encontrada. Rode o instalar.command de novo.")
        return False
    BASE.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "ab")
    subprocess.Popen([py, str(APP / "server.py")], cwd=str(APP), stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                     start_new_session=True)  # sobrevive ao fechamento do script
    for _ in range(40):
        if up():
            return True
        time.sleep(0.25)
    print(f"Artlist: o servidor não respondeu. Veja {LOG}")
    return False


if up() or start_server():
    subprocess.Popen(["open", URL])
