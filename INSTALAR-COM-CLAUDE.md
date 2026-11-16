# Instalar o "Artlist → Resolve" (instruções para o Claude)

**Claude: o usuário anexou este arquivo para você instalar o app "Artlist → Resolve" no Mac dele e guiá-lo nos passos
que dependem dele.** Siga as instruções abaixo, na ordem. Rode você mesmo os comandos (o usuário aprova os pedidos de
permissão do app) e, entre os passos, diga em uma frase curta o que foi feito e o que vem a seguir. Fale em português.

Se o usuário escreveu "atualizar" (ou algo parecido) junto com o arquivo, pule direto para a seção **Atualizar**, no fim.

## O que é (para você explicar em uma ou duas frases)
Um painel dentro do DaVinci Resolve Studio para buscar músicas e SFX do catálogo do Artlist (por descrição, referência
ou mood), ouvir com waveform, marcar um trecho (In/Out) e importar no Media Pool ou inserir direto na timeline, no
playhead. Usa o conector Artlist do Claude da própria conta do usuário: o plano, o limite de downloads e a licença do
Artlist são dele. Código: https://github.com/dynyamaguti/artlist-resolve

## Regras (valem o tempo todo)
- **Nunca peça, leia nem digite senhas.** A senha de administrador é digitada pelo usuário numa janela do macOS. Não use `sudo` no Bash.
- Não mexa em nada fora de `~/ArtlistResolve`, `~/Library/Application Support/ArtlistResolve` e da pasta de scripts do Resolve (`~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility`). Não apague plugins, projetos nem arquivos do usuário. Existe um plugin antigo `com.trendsy.artlist` na pasta de plugins do Resolve: **deixe como está**.
- **Não baixe músicas nem SFX do Artlist** (cada download conta no limite diário do usuário). Não rode buscas de teste.
- Relate com honestidade o resultado de cada passo: o que funcionou e o que falhou, com a mensagem de erro.
- Se um passo falhar, diga o erro e proponha o próximo passo. Não pule passos nem invente resultados.

## Passos

**1. Pré-requisitos.** Confirme: macOS; DaVinci Resolve instalado (`ls "/Applications/DaVinci Resolve"`); Python 3 (`python3 --version`). Se for a versão gratuita do Resolve (sem "Studio"), avise que o painel exige o **Resolve Studio** (a versão gratuita não aceita scripts externos) e pergunte se quer continuar.

**2. Baixar o app.** Rode `git clone https://github.com/dynyamaguti/artlist-resolve.git ~/ArtlistResolve` (se a pasta já existir, `git -C ~/ArtlistResolve pull`). O repositório é público. Se o `git` pedir para instalar as Command Line Tools, deixe o usuário concluir a janela da Apple e tente de novo.

**3. Instalar.** Rode `cd ~/ArtlistResolve && zsh ./instalar.command --sim`.
Avise o usuário antes: **uma janela do macOS vai pedir a senha de administrador** para instalar o painel no Resolve, e ele mesmo a digita. Se ele cancelar ou não for administrador, rode de novo com `zsh ./instalar.command --sim --sem-painel` (o app funcionará pelo menu *Workspace → Scripts → Artlist*, sem o painel flutuante).

**4. Login do Claude CLI.** Rode `security find-generic-password -s "Claude Code-credentials" >/dev/null 2>&1 && echo ok || echo sem-login`.
Se der `sem-login`, rode `claude auth login` e peça ao usuário para concluir o login no navegador que vai abrir (é a conta Claude Pro/Team dele). Não use `claude auth status` como prova: dentro do app Claude ele pode aparecer logado mesmo sem login salvo para o painel.

**5. Conector Artlist (só o usuário faz).** Rode `open https://claude.ai` e peça ao usuário para:
  a. Ir em **Configurações → Conectores** e conectar o **Artlist** com a conta Artlist dele.
  b. Abrir o conector Artlist (Configurações → Conectores → Artlist), rolar até a lista de ferramentas e deixar em **Permitir** (ícone ✓, o primeiro de cada linha) estas: **Search Artlist music catalog**, **Search Artlist SFX catalog**, **Get Artlist track details** e a de **download** da faixa. Sem isso a busca e a importação falham, porque o painel roda sem ninguém para aprovar cada uso.
  Espere ele confirmar que terminou.

**6. Resolve (só o usuário faz).** Peça para:
  a. Abrir o DaVinci Resolve Studio → *Preferências → Sistema → Geral* → **"Uso de script externo" = Local** → Salvar.
  b. Fechar o Resolve por completo (⌘Q) e abrir de novo, com um projeto e uma timeline.

**7. Abrir o painel.** Peça para ir em **Workspace → Workflow Integrations → Artlist Search**. Se esse item não existir, a instalação do painel foi pulada ou o Resolve não foi reiniciado; o botão alternativo é **Workspace → Scripts → Artlist**, que abre o mesmo painel no navegador.
O painel tem, no topo, um diagnóstico com ✓/✗ de cada requisito (Claude CLI, login, conector Artlist, áudio do macOS, Resolve). Peça ao usuário para te dizer o que aparece e ajude a resolver cada ✗.

**8. Encerrar.** Quando o diagnóstico estiver todo ✓, resuma em poucas linhas: o que foi instalado, onde, e como usar (buscar → ouvir → arrastar na waveform para marcar In/Out → "Inserir no playhead"). Diga que a pasta de downloads (padrão `~/Music/Artlist-Resolve`) pode ser trocada na própria tela do app, no botão "Alterar pasta…".

## Atualizar
Só se o usuário pediu para atualizar: rode `git -C ~/ArtlistResolve pull` e depois `cd ~/ArtlistResolve && zsh ./instalar.command --sim --sem-painel`. Se o `README.md` ou o `git log` indicar que o painel do Resolve mudou, rode sem o `--sem-painel` (a janela do macOS pedirá a senha; o usuário digita). Peça para reiniciar o Resolve e diga em poucas linhas o que mudou (`git -C ~/ArtlistResolve log --oneline -5`). Não mexa em mais nada.

## Referência: o que o instalador faz
- Confere Python 3 e o Claude Code CLI (instala o CLI com o instalador oficial da Anthropic, se faltar).
- Copia o app para `~/Library/Application Support/ArtlistResolve/app` e o botão para `.../Fusion/Scripts/Utility/Artlist.py`.
- Instala o painel em `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/com.trendsy.artlistsearch` (pasta protegida; senha pela janela do macOS).
- Não envia dados a servidores além das consultas ao Artlist pelo conector da conta do próprio usuário.
