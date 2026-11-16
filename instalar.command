#!/bin/zsh
# Instalador — Artlist → Resolve (macOS). Duplo clique para instalar ou atualizar.
cd "$(dirname "$0")" || exit 1
SRC="$PWD"
BASE="$HOME/Library/Application Support/ArtlistResolve"
DEST="$BASE/app"
RES="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.claude/local:$PATH"

step() { print -P "\n%F{yellow}▸%f %B$*%b"; }
ok()   { print -P "  %F{green}✓%f $*"; }
warn() { print -P "  %F{red}✗%f $*"; }
ask()  { local r; read -q "r?  $1 [s/N] "; local rc=$?; print; return $rc; }

[[ "$(uname)" == "Darwin" ]] || { warn "Este instalador é só para macOS."; exit 1; }

step "Python 3"
if xcode-select -p >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1; then
  ok "$(python3 --version 2>&1)"
else
  warn "Falta o Python 3 (Command Line Tools). Abrindo o instalador da Apple…"
  xcode-select --install
  print "  Quando terminar, rode este instalador de novo."; exit 1
fi

step "ffmpeg"
if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  ok "encontrado"
elif command -v brew >/dev/null 2>&1; then
  ask "Instalar ffmpeg com o Homebrew?" && brew install ffmpeg || warn "Sem ffmpeg o app não gera waveforms nem corta trechos."
else
  warn "Instale o Homebrew (https://brew.sh) e rode: brew install ffmpeg"
fi

step "Claude Code CLI"
if command -v claude >/dev/null 2>&1; then
  ok "$(claude --version 2>&1 | head -1)"
else
  warn "Claude Code CLI não encontrado."
  ask "Instalar agora (instalador oficial da Anthropic)?" && curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
fi

step "Copiando o app"
pkill -f "ArtlistResolve/app/server.py" 2>/dev/null
mkdir -p "$DEST" && cp -R "$SRC/server.py" "$SRC/static" "$SRC/README.md" "$DEST/" && ok "$DEST"

step "Botão dentro do DaVinci Resolve"
mkdir -p "$RES" && cp "$SRC/resolve/Artlist.py" "$RES/Artlist.py" && ok "Workspace ▸ Scripts ▸ Artlist (reinicie o Resolve se ele estiver aberto)"

step "Painel dentro do Resolve (Workspace ▸ Workflow Integrations ▸ Artlist Search)"
PLG="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins"
PID="com.trendsy.artlistsearch"
WI_NODE="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Workflow Integrations/Examples/SamplePlugin/WorkflowIntegration.node"
if [[ ! -d "$PLG" ]]; then
  warn "Pasta de plugins do Resolve não encontrada (Resolve Studio instalado?). Pulando — o botão do menu Scripts continua valendo."
elif ask "Instalar o painel flutuante dentro do Resolve? (pede a senha do Mac)"; then
  sudo mkdir -p "$PLG/$PID" \
    && sudo cp -R "$SRC/resolve/plugin/$PID/." "$PLG/$PID/" \
    && { [[ -f "$WI_NODE" ]] && sudo cp "$WI_NODE" "$PLG/$PID/" || true; } \
    && ok "Instalado. Reinicie o Resolve: Workspace ▸ Workflow Integrations ▸ Artlist Search" \
    || warn "Não foi possível instalar o painel (senha negada?). O botão do menu Scripts continua valendo."
else
  print "  Pulado. O botão do menu Scripts continua valendo."
fi

print -P "\n%F{green}%BInstalado.%b%f Falta só (uma vez):"
print "  1. Terminal: rode  claude  e faça login com a sua conta Claude (se ainda não fez)."
print "  2. claude.ai ▸ Configurações ▸ Conectores: conecte o Artlist."
print "  3. Resolve ▸ Preferências ▸ Sistema ▸ Geral ▸ “Uso de script externo” = Local."
print "  4. Use: Resolve ▸ Workspace ▸ Workflow Integrations ▸ Artlist Search (painel) ou"
print "     Workspace ▸ Scripts ▸ Artlist (navegador). A tela mostra o que ainda faltar."
print "  Downloads ficam em: ~/Music/Artlist-Resolve"

if ask "Abrir o app agora?"; then
  PY="$(command -v python3)"
  (cd "$DEST" && nohup "$PY" server.py >"$BASE/server.log" 2>&1 &)
  sleep 2; open "http://127.0.0.1:8765"
fi
