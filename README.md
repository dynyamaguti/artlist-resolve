# Artlist → Resolve

App local para buscar música/SFX do Artlist e mandar direto para o DaVinci Resolve Studio (macOS).

## Instalar (cada editor, uma vez)
1. Baixe/clone este repositório e dê **duplo clique em `instalar.command`**
   (se o macOS bloquear: clique direito → Abrir).
   Ele confere Python, ffmpeg e Claude Code CLI, copia o app para
   `~/Library/Application Support/ArtlistResolve/app` e instala o botão no Resolve.
2. **Terminal:** rode `claude` e faça login com a sua conta Claude (Pro/Team).
3. **claude.ai → Configurações → Conectores:** conecte o **Artlist** (login da sua conta Artlist).
4. **Resolve → Preferências → Sistema → Geral → “Uso de script externo” = Local.** Reinicie o Resolve.

## Usar
**Resolve → Workspace → Scripts → Artlist** abre o dashboard (e sobe o servidor se precisar).
No topo da página, o painel de diagnóstico mostra o que ainda falta configurar.

Busque (descrever, referência, moods; música ou SFX), ouça, selecione um trecho
(arraste na waveform, `I`/`O` tocando, ou ajuste as bordas) e:
- **Importar no Media Pool** → bin "Artlist".
- **Inserir no playhead** → trilha de áudio escolhida, no timecode atual da timeline
  (se a trilha estiver ocupada, usa a próxima livre).

## Como funciona
- **Busca**: o servidor chama `claude -p` (modelo haiku) com as ferramentas do conector Artlist da conta
  de quem está usando. O Claude só traduz o pedido em consultas; as faixas exibidas vêm direto do catálogo.
  Cada editor usa o próprio plano, limite de downloads e licença do Artlist.
- **Waveform/preview**: preview do Artlist remuxado para M4A, cache em `~/Library/Application Support/ArtlistResolve/cache`.
- **Importar**: `download_track` (WAV) — **conta no limite diário do Artlist**. Cada faixa é baixada uma vez
  (`~/Music/Artlist-Resolve/index.json`); reimportar não baixa de novo. Trechos In/Out viram arquivos em `trechos/`.
- Os áudios nunca entram no repositório (`.gitignore`).

## Atualizar
Baixe a versão nova e rode `instalar.command` de novo (ele encerra o servidor antigo e copia os arquivos).

## Desenvolvimento
`./iniciar.command` roda direto desta pasta. Variáveis: `PORT` (8765), `ARTLIST_MODEL` (haiku),
`ARTLIST_DOWNLOADS`, `ARTLIST_HOME`.
