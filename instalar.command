#!/bin/zsh
# Instalador — Artlist → Resolve (macOS). Duplo clique ou:  ./instalar.command [--sim] [--sem-painel]
#   --sim          não faz perguntas (usado quando o Claude instala por você)
#   --sem-painel   pula o painel flutuante do Resolve (que exige senha de administrador)
cd "$(dirname "$0")" || exit 1
SRC="$PWD"
BASE="$HOME/Library/Application Support/ArtlistResolve"
DEST="$BASE/app"
RES="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.claude/local:$PATH"

AUTO=0; NOPANEL=0
for a in "$@"; do case "$a" in --sim) AUTO=1 ;; --sem-painel) NOPANEL=1 ;; esac; done

step() { print -P "\n%F{yellow}▸%f %B$*%b"; }
ok()   { print -P "  %F{green}✓%f $*"; }
warn() { print -P "  %F{red}✗%f $*"; }
# ask "pergunta" [manual]: com --sim responde sim sozinho, exceto perguntas marcadas "manual".
ask()  {
  if (( AUTO )); then print "  $1 → ${${2:+não (automático)}:-sim (automático)}"; [[ -z "$2" ]]; return; fi
  local r; print -n "  $1 [s/N] (digite s e Enter) "; read -r r; [[ "$r" == [sSyY]* ]]
}

[[ "$(uname)" == "Darwin" ]] || { warn "Este instalador é só para macOS."; exit 1; }

step "Python 3"
if xcode-select -p >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1; then
  ok "$(python3 --version 2>&1)"
else
  warn "Falta o Python 3 (Command Line Tools). Abrindo o instalador da Apple…"
  xcode-select --install
  print "  Quando terminar, rode este instalador de novo."; exit 1
fi

step "Claude Code CLI"
if command -v claude >/dev/null 2>&1; then
  ok "$(claude --version 2>&1 | head -1)"
else
  warn "Claude Code CLI não encontrado."
  ask "Instalar agora (instalador oficial da Anthropic)?" && curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
  command -v claude >/dev/null 2>&1 && ok "instalado" || warn "Não consegui instalar o CLI. Veja https://claude.ai/download"
fi

step "Copiando o app"
pkill -f "ArtlistResolve/app/server.py" 2>/dev/null
mkdir -p "$DEST" && cp -R "$SRC/server.py" "$SRC/static" "$SRC/README.md" "$DEST/" && ok "$DEST"

step "Botão dentro do DaVinci Resolve"
mkdir -p "$RES" && cp "$SRC/resolve/Artlist.py" "$RES/Artlist.py" && ok "Workspace ▸ Scripts ▸ Artlist (reinicie o Resolve se ele estiver aberto)"

step "Painel dentro do Resolve (Workspace ▸ Workflow Integrations ▸ Artlist Search)"
PLG="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins"
PID="com.trendsy.artlistsearch"
PSRC="$SRC/resolve/plugin/$PID"
WI_NODE="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Workflow Integrations/Examples/SamplePlugin/WorkflowIntegration.node"
if (( NOPANEL )); then
  print "  Pulado (--sem-painel). O botão do menu Scripts continua valendo."
elif [[ ! -d "$PLG" ]]; then
  warn "Pasta de plugins do Resolve não encontrada (Resolve Studio instalado?). Pulando — o botão do menu Scripts continua valendo."
elif ask "Instalar o painel flutuante dentro do Resolve? (o macOS vai pedir a senha de administrador numa janela)"; then
  # A pasta de plugins é protegida: a senha é pedida pela janela nativa do macOS (funciona sem Terminal).
  # Permissões 755/644 e só os 3 arquivos pelo nome: o Resolve roda como o usuário e precisa LER os arquivos
  # (cp de disco externo deixava 700 do root e o plugin não aparecia; também traz lixo ._*).
  TMPS="$(mktemp /tmp/artlist-plugin.XXXXXX)"
  cat > "$TMPS" <<EOF
#!/bin/zsh
set -e
mkdir -p "$PLG/$PID"
cp "$PSRC/main.js" "$PSRC/manifest.xml" "$PSRC/package.json" "$PLG/$PID/"
[ -f "$WI_NODE" ] && cp "$WI_NODE" "$PLG/$PID/" || true
find "$PLG/$PID" -maxdepth 1 -name '._*' -delete
chmod 755 "$PLG/$PID"
chmod 644 "$PLG/$PID"/*
EOF
  if osascript -e "do shell script \"/bin/zsh $TMPS\" with administrator privileges with prompt \"O Artlist Resolve vai instalar o painel dentro do DaVinci Resolve.\"" >/dev/null 2>&1; then
    ok "Instalado. Reinicie o Resolve: Workspace ▸ Workflow Integrations ▸ Artlist Search"
  else
    warn "Não foi possível instalar o painel (senha cancelada?). O botão do menu Scripts continua valendo."
  fi
  rm -f "$TMPS"
else
  print "  Pulado. O botão do menu Scripts continua valendo."
fi

step "Login no Claude"
if command -v claude >/dev/null 2>&1 && ! claude auth status 2>/dev/null | grep -q '"loggedIn": true'; then
  warn "Sem login no Claude neste Mac."
  if (( AUTO )); then
    print "  Faça o login depois (botão no painel do Artlist, ou no Terminal: claude auth login)."
  elif ask "Fazer login agora? (abre o navegador)"; then
    claude auth login
  fi
else
  ok "ok"
fi

print -P "\n%F{green}%BInstalado.%b%f Falta só (uma vez):"
print "  1. Login no Claude com a sua conta (Pro/Team), se ainda não fez."
print "  2. claude.ai ▸ Configurações ▸ Conectores: conecte o Artlist e deixe em “Permitir” (✓) as"
print "     ferramentas de busca de músicas, busca de SFX, detalhes da faixa e download."
print "  3. Resolve ▸ Preferências ▸ Sistema ▸ Geral ▸ “Uso de script externo” = Local. Reinicie o Resolve."
print "  4. Use: Resolve ▸ Workspace ▸ Workflow Integrations ▸ Artlist Search (painel) ou"
print "     Workspace ▸ Scripts ▸ Artlist (navegador). A tela mostra o que ainda faltar."
print "  Downloads: ~/Music/Artlist-Resolve (dá para trocar a pasta na tela do app)"

if ask "Abrir o app agora?" manual; then
  PY="$(command -v python3)"
  (cd "$DEST" && nohup "$PY" server.py >"$BASE/server.log" 2>&1 &)
  sleep 2; open "http://127.0.0.1:8765"
fi
