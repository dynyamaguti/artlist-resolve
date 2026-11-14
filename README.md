# Artlist → Resolve

App local para buscar música/SFX do Artlist e mandar direto para o DaVinci Resolve.

## Usar
1. Abra o DaVinci Resolve Studio (preferências → Geral → "Uso de script externo": **Local**).
2. Duplo clique em `iniciar.command` (ou `python3 server.py`) e abra http://127.0.0.1:8765.
3. Busque, ouça, selecione um trecho (arraste na waveform, ou `I`/`O`) e:
   - **Importar no Media Pool** → bin "Artlist".
   - **Inserir no playhead** → trilha de áudio escolhida, no timecode atual da timeline.

## Como funciona
- **Busca**: o servidor chama `claude -p` (modelo haiku) com as ferramentas do conector Artlist da sua conta.
  O Claude só traduz o pedido em consultas; as faixas exibidas vêm direto do catálogo.
  Modos: descrever, referência (link/ID/título/artista) e moods (com sugestão por cena).
- **Waveform/preview**: baixados do preview do Artlist, remuxados para M4A e cacheados em `cache/`.
- **Importar**: `download_track` (WAV) — **conta no limite diário do Artlist**. Cada faixa é baixada uma vez
  (`downloads/index.json`); reimportar não baixa de novo. Trechos In/Out são cortados em `downloads/trechos/`.
- Se a trilha escolhida estiver ocupada no ponto do playhead, usa a próxima livre (o Resolve descarta em
  silêncio inserções sobrepostas).

## Variáveis
`PORT` (8765) · `ARTLIST_MODEL` (haiku) · `ARTLIST_DOWNLOADS` (pasta dos downloads).
