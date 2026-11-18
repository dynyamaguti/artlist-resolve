#!/bin/zsh
# Duplo clique para abrir o app Busca Busca Trilhas e SFX.
cd "$(dirname "$0")"
(sleep 2; open "http://127.0.0.1:8765") &
exec python3 server.py
