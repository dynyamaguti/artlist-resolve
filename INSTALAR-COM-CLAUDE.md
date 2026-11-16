# Instalar pelo Claude

Para o editor: abra o app **Claude** (aba **Code**), abra uma pasta qualquer (ex.: a sua pasta pessoal) e **cole a mensagem abaixo**.
O Claude instala o app e te guia nos passos que só você pode fazer (senha, login, conector).

> **Quem distribui:** antes, dê acesso ao repositório (GitHub → Settings → Collaborators) para o editor,
> e confirme que ele tem Resolve **Studio**, Claude Pro/Team e conta Artlist.

---

## Mensagem para colar (instalar)

```
Instale o app "Artlist → Resolve" neste Mac e me guie nos passos que dependem de mim.

Repositório: https://github.com/dynyamaguti/artlist-resolve (privado; se eu não tiver acesso, me avise e pare).

Faça nesta ordem:

1. Baixe para ~/ArtlistResolve: tente `gh repo clone dynyamaguti/artlist-resolve ~/ArtlistResolve`; se o gh não existir ou falhar, tente `git clone https://github.com/dynyamaguti/artlist-resolve.git ~/ArtlistResolve`. Se a pasta já existir, rode `git -C ~/ArtlistResolve pull`. Se der erro de acesso, me diga que preciso pedir o convite do repositório e pare.

2. Leia o README.md dessa pasta.

3. Rode `cd ~/ArtlistResolve && zsh ./instalar.command --sim`. Uma janela do macOS vai pedir a MINHA senha de administrador para instalar o painel no DaVinci Resolve: eu mesmo digito. Você nunca pede nem digita senha e não usa sudo no Bash. Se eu cancelar ou não for administrador, rode de novo com `zsh ./instalar.command --sim --sem-painel`.

4. Confira se há login do Claude CLI salvo neste Mac: `security find-generic-password -s "Claude Code-credentials" >/dev/null 2>&1 && echo ok || echo sem-login`. Se der "sem-login", rode `claude auth login` e me peça para concluir o login no navegador que vai abrir. (Não use `claude auth status` como prova: dentro do app Claude ele pode aparecer logado mesmo sem login salvo.)

5. Abra https://claude.ai com `open` e me peça para ir em Configurações → Conectores e conectar o **Artlist** com a MINHA conta Artlist; espere eu confirmar.

6. Me peça para: abrir o DaVinci Resolve Studio → Preferências → Sistema → Geral → "Uso de script externo" = Local; depois fechar o Resolve por completo (⌘Q) e abrir de novo com um projeto e uma timeline.

7. Me diga para abrir Workspace → Workflow Integrations → Artlist Search. O painel mostra um diagnóstico com ✓/✗ do que ainda falta; me ajude com o que aparecer.

Regras: não mexa em nada fora de ~/ArtlistResolve, ~/Library/Application Support/ArtlistResolve e da pasta de scripts do Resolve; não apague plugins nem arquivos meus; relate com honestidade o resultado de cada passo (o que funcionou e o que falhou); não baixe músicas do Artlist (cada download conta no meu limite diário).
```

---

## Mensagem para colar (atualizar)

```
Atualize o app "Artlist → Resolve": rode `git -C ~/ArtlistResolve pull` e depois `cd ~/ArtlistResolve && zsh ./instalar.command --sim --sem-painel`. Se o README ou o CHANGELOG disser que o painel do Resolve mudou, rode sem o `--sem-painel` (a janela do macOS vai pedir a minha senha; eu digito). Depois me peça para reiniciar o Resolve. Não mexa em mais nada e me diga o que mudou.
```

---

## O que a instalação faz (para você conferir o que o Claude vai rodar)
- `instalar.command` confere o Python 3 e o Claude Code CLI (instala o CLI com o instalador oficial da Anthropic, se faltar),
  copia o app para `~/Library/Application Support/ArtlistResolve/app` e o botão para a pasta de scripts do Resolve
  (`.../Fusion/Scripts/Utility/Artlist.py`).
- O painel flutuante vai para `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/`
  (pasta protegida: a senha é pedida pela janela do macOS).
- Nada é enviado a servidores além das consultas ao Artlist pelo conector da própria conta do editor.
