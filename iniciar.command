#!/bin/zsh
# Duplo clique para abrir o app Artlist → Resolve.
cd "$(dirname "$0")"
(sleep 2; open "http://127.0.0.1:8765") &
exec python3 server.py
