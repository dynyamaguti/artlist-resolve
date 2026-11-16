#!/usr/bin/env python3
"""Artlist → DaVinci Resolve: servidor local.

- Busca no catálogo Artlist via Claude CLI (conector MCP da sua conta).
- Serve preview de áudio + waveform (ffmpeg).
- Baixa a faixa (download_track conta no limite diário!) e importa no Resolve.

Uso:  python3 server.py   →  http://127.0.0.1:8765
"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, threading, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from array import array
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Dados por usuário (cada editor tem os seus; nada disso vai para o repositório).
DATA_DIR = Path(os.environ.get("ARTLIST_HOME", Path.home() / "Library/Application Support/ArtlistResolve"))
CACHE = DATA_DIR / "cache"
CACHE.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = DATA_DIR / "config.json"
INDEX_PATH = DATA_DIR / "downloads-index.json"  # faixa já baixada → arquivo (vale em qualquer pasta)
DEFAULT_DOWNLOADS = Path(os.environ.get("ARTLIST_DOWNLOADS", Path.home() / "Music/Artlist-Resolve"))


def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (OSError, ValueError):
        return {}


def get_downloads():
    """Pasta de downloads escolhida pelo editor (config.json) ou o padrão."""
    p = load_config().get("downloads")
    return Path(p) if p else DEFAULT_DOWNLOADS


def ensure_downloads():
    d = get_downloads()
    try:
        (d / "trechos").mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"Pasta de downloads indisponível ({d}): {e.strerror or e}. "
                           "Escolha outra em “Alterar pasta” (o disco está conectado?).")
    return d


def load_index():
    idx = {}
    for p in (get_downloads() / "index.json", DEFAULT_DOWNLOADS / "index.json", INDEX_PATH):  # o global vence
        try:
            idx.update(json.loads(p.read_text()))
        except (OSError, ValueError):
            pass
    return idx

PORT = int(os.environ.get("PORT", "8765"))
MODEL = os.environ.get("ARTLIST_MODEL", "haiku")
RESOLVE_MODULES = os.environ.get(
    "RESOLVE_SCRIPT_MODULES",
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")

# Quando o servidor é aberto pelo Resolve/Finder o PATH é mínimo: procura os binários nos lugares comuns.
EXTRA_DIRS = [str(HERE / "bin"), "/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local/bin"),
              str(Path.home() / ".claude/local"), "/usr/bin"]
EXTRA_DIRS += sorted(glob.glob(str(Path.home() / ".nvm/versions/node/*/bin")), reverse=True)
ENV = dict(os.environ, PATH=os.pathsep.join(EXTRA_DIRS + [os.environ.get("PATH", "")]))


def find_bin(name):
    p = shutil.which(name, path=ENV["PATH"])
    return p


CLAUDE = find_bin("claude")
FFMPEG = find_bin("ffmpeg") or "ffmpeg"
FFPROBE = find_bin("ffprobe") or "ffprobe"

# Nome das ferramentas do conector Artlist: depende do nome do conector na conta de cada pessoa
# (ex.: "claude.ai artlist" → mcp__claude_ai_artlist__*). Detectado na primeira busca.
T_MUSIC = T_SFX = T_GET = T_DL = ""
_prefix_ready = False
_prefix_lock = threading.Lock()


def set_prefix(prefix):
    global T_MUSIC, T_SFX, T_GET, T_DL
    T_MUSIC, T_SFX = prefix + "search_music", prefix + "search_sfx"
    T_GET, T_DL = prefix + "get_track", prefix + "download_track"


set_prefix("mcp__claude_ai_artlist__")


def detect_artlist():
    """Lê `claude mcp list`. Devolve (nome_do_servidor, status) do conector Artlist, ou (None, motivo)."""
    if not CLAUDE:
        return None, "Claude Code CLI não encontrado"
    p = subprocess.run([CLAUDE, "mcp", "list"], capture_output=True, text=True, timeout=90, cwd="/tmp", env=ENV)
    for line in p.stdout.splitlines():
        m = re.match(r"^(.*?): (\S+) - (.*)$", line.strip())
        if m and "artlist" in m.group(1).lower():
            return m.group(1), m.group(3).strip()
    return None, "conector Artlist não encontrado nesta conta"


def ensure_prefix():
    global _prefix_ready
    with _prefix_lock:
        if _prefix_ready:
            return
        name, _ = detect_artlist()
        if name:
            set_prefix("mcp__" + re.sub(r"[^A-Za-z0-9_-]", "_", name) + "__")
            _prefix_ready = True

resolve_lock = threading.Lock()
peaks_sem = threading.Semaphore(3)
dl_lock = threading.Lock()


# ───────────────────────── Claude CLI ─────────────────────────
def run_claude(prompt, tools, timeout=150):
    if not CLAUDE:
        raise RuntimeError("Claude Code CLI não encontrado. Rode o instalar.command ou veja o diagnóstico.")
    cmd = [CLAUDE, "-p", prompt, "--model", MODEL, "--output-format", "stream-json", "--verbose"]
    if tools:
        cmd += ["--allowedTools", ",".join(tools)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd="/tmp", env=ENV)
    names, results, final = {}, [], ""
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        t = ev.get("type")
        if t == "assistant":
            for c in ev["message"].get("content", []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    names[c["id"]] = c["name"]
        elif t == "user":
            content = ev["message"].get("content")
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        body = c.get("content")
                        if isinstance(body, list):
                            body = "".join(x.get("text", "") for x in body if isinstance(x, dict))
                        results.append((names.get(c.get("tool_use_id"), ""), body or ""))
        elif t == "result":
            final = ev.get("result", "") or ""
    if proc.returncode != 0 and not final:
        raise RuntimeError("Claude CLI falhou: " + ((proc.stderr or proc.stdout).strip()[:300] or f"código {proc.returncode}"))
    return results, final


def to_seconds(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.fullmatch(r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", str(v).strip())
    if m:
        return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    try:
        return float(v)
    except ValueError:
        return None


def extract_tracks(tool_name, text):
    kind = "sfx" if tool_name.endswith("search_sfx") else "music" if tool_name.endswith("search_music") else None
    if not kind:
        return []
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = None
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "songId" in v[0]:
                rows = v
                break
    elif isinstance(data, list):
        rows = data
    out = []
    for r in rows or []:
        url = r.get("playableUrl") or ""
        out.append({
            "id": f"{kind}:{r.get('songId')}",
            "songId": str(r.get("songId")),
            "kind": kind,
            "title": r.get("title", "?"),
            "artist": r.get("artist", ""),
            "duration": to_seconds(r.get("duration")),
            "bpm": r.get("bpm"),
            "audioKey": url.split("#")[0],
            "hookIn": r.get("hookStartSeconds"),
            "hookOut": r.get("hookEndSeconds"),
            "artwork": r.get("artworkUrl"),
            "trackUrl": r.get("trackUrl"),
            "tags": r.get("suggestedTags"),
        })
    return out


def api_search(body):
    ensure_prefix()
    kind = "sfx" if body.get("kind") == "sfx" else "music"
    mode = body.get("mode", "describe")
    text = (body.get("text") or "").strip()[:500]
    moods = [m[:40] for m in (body.get("moods") or [])][:8]
    f = body.get("filters") or {}
    cons = []
    if kind == "music":
        if f.get("vocals") in ("INSTRUMENTAL", "VOCAL"):
            cons.append(f"vocals={f['vocals']}")
        if f.get("bpmMin"): cons.append(f"bpmMin={int(f['bpmMin'])}")
        if f.get("bpmMax"): cons.append(f"bpmMax={int(f['bpmMax'])}")
        if f.get("durMin"): cons.append(f"durationMin={int(f['durMin'])}")
        if f.get("durMax"): cons.append(f"durationMax={int(f['durMax'])}")
    tool = T_SFX if kind == "sfx" else T_MUSIC
    tools = [tool, T_GET]
    base = (
        "Você é o motor de busca de um app para editores de vídeo. Use SOMENTE as ferramentas do conector Artlist "
        f"({tool}, {T_GET}) — nunca as do Envato nem outras. Não baixe nada. O catálogo é em inglês: traduza e "
        "varie os termos. Faça de 1 a 3 buscas complementares com perPage 12 (use filtros de BPM/duração/vocal "
        "quando o pedido sugerir). Ao terminar, responda UMA frase curta em português dizendo como interpretou o "
        "pedido e quais consultas usou. Não liste as faixas.\n\n"
    )
    if cons:
        base += f"Filtros obrigatórios em toda busca: {', '.join(cons)}.\n"
    if mode == "reference":
        base += (
            "MODO REFERÊNCIA: o texto abaixo é uma referência (link do Artlist, ID, título de faixa, artista ou "
            "estilo). Se houver link/ID do Artlist, chame get_track para ler gênero/mood/BPM, depois busque faixas "
            "parecidas e exclua a própria faixa. Se for título/artista, busque-o primeiro, use as características "
            "da faixa encontrada e depois busque parecidas.\n"
        )
        base += f"Referência: <<{text}>>\n"
    elif mode == "moods":
        base += "MODO MOODS: combine os moods escolhidos numa busca coerente.\n"
        base += f"Moods: {', '.join(moods)}\n"
        if text:
            base += f"Contexto extra: <<{text}>>\n"
    else:
        base += "MODO DESCRITIVO: interprete a cena/pedido abaixo em linguagem natural.\n"
        base += f"Pedido: <<{text}>>\n"
    results, final = run_claude(base, tools)
    seen, tracks = set(), []
    # intercala resultados de buscas diferentes para dar variedade
    per_call = [extract_tracks(n, t) for n, t in results]
    per_call = [p for p in per_call if p]
    i = 0
    while any(i < len(p) for p in per_call):
        for p in per_call:
            if i < len(p) and p[i]["id"] not in seen:
                seen.add(p[i]["id"])
                tracks.append(p[i])
        i += 1
    ref_id = re.search(r"/(\d+)(?:\?|$)", text) if mode == "reference" else None
    if ref_id:
        tracks = [t for t in tracks if t["songId"] != ref_id.group(1)]
    return {"tracks": tracks[:30], "interpretation": final.strip()}


def api_suggest(body):
    scene = (body.get("text") or "").strip()[:500]
    prompt = (
        "Sugira 8 moods/estilos musicais (rótulo curto em português) para a cena de vídeo abaixo. Responda SOMENTE "
        'com um array JSON de strings, sem texto extra, ex: ["Épico","Inspirador"].\n'
        f"Cena: <<{scene}>>"
    )
    _, final = run_claude(prompt, [], timeout=60)
    m = re.search(r"\[.*\]", final, re.S)
    try:
        return {"moods": [str(x) for x in json.loads(m.group(0))][:10]}
    except Exception:
        return {"moods": []}


# ───────────────────────── Áudio / waveform ─────────────────────────
def check_host(url):
    host = urllib.parse.urlparse(url).hostname or ""
    if not (host == "artlist.io" or host.endswith(".artlist.io")):
        raise ValueError("host não permitido")


def cached_audio(url):
    check_host(url)
    key = hashlib.sha1(url.encode()).hexdigest()
    path = CACHE / f"{key}.m4a"
    if not path.exists():
        raw = CACHE / f"{key}.aac"
        req = urllib.request.Request(url, headers={"User-Agent": "artlist-resolve/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(raw, "wb") as fh:
            shutil.copyfileobj(r, fh)
        # ADTS cru não tem duração exata no navegador; remux para M4A (sem recodificar) corrige o alinhamento.
        tmp = CACHE / f"{key}.tmp.m4a"
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(raw), "-c:a", "copy", "-movflags", "+faststart", str(tmp)],
                       check=True)
        tmp.rename(path)
        raw.unlink(missing_ok=True)
    return path


def audio_duration(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def api_peaks(url, n=900):
    path = cached_audio(url)
    pk = path.with_suffix(".peaks2.json")  # v2: duração via ffprobe do M4A
    if pk.exists():
        return json.loads(pk.read_text())
    with peaks_sem:
        raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", "4000", "-f", "s16le", "-"],
                             capture_output=True).stdout
    a = array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    step = max(1, len(a) // n)
    peaks = [max(abs(min(a[i:i + step])), abs(max(a[i:i + step]))) / 32768 for i in range(0, len(a) - step + 1, step)]
    top = max(peaks) or 1
    data = {"peaks": [round(p / top, 3) for p in peaks], "duration": audio_duration(path) or len(a) / 4000}
    pk.write_text(json.dumps(data))
    return data


# ───────────────────────── Download + corte ─────────────────────────
def safe_name(s):
    return re.sub(r"[^\w\-. ()\[\]]+", "_", s).strip()[:80] or "track"


def download_licensed(song_id, kind, title):
    """Baixa via download_track (conta no limite diário). Reutiliza arquivo se já baixado."""
    with dl_lock:
        idx = load_index()
        key = f"{kind}:{song_id}"
        if key in idx and Path(idx[key]).exists():
            return Path(idx[key]), True
        folder = ensure_downloads()
        ensure_prefix()
        prompt = (
            f"Chame a ferramenta {T_DL} (conector Artlist, não Envato) com songId '{song_id}', kind '{kind}' e "
            "format 'wav'. Depois responda apenas com o link retornado."
        )
        results, final = run_claude(prompt, [T_DL], timeout=120)
        blob = " ".join(t for n, t in results if n.endswith("download_track")) or final
        m = re.search(r"https?://[^\s\"'\\<>]+", blob)
        if not m:
            raise RuntimeError("download_track não retornou link: " + (final or blob)[:200])
        req = urllib.request.Request(m.group(0), headers={"User-Agent": "artlist-resolve/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            ctype = r.headers.get("Content-Type", "")
            cd = r.headers.get("Content-Disposition", "")
            ext = ".wav"
            mm = re.search(r'\.(wav|mp3|aac|m4a)', cd + m.group(0).split("?")[0], re.I)
            if mm:
                ext = "." + mm.group(1).lower()
            elif "mpeg" in ctype:
                ext = ".mp3"
            dest = folder / f"{safe_name(title)} ({song_id}){ext}"
            with open(dest, "wb") as fh:
                shutil.copyfileobj(r, fh)
        idx[key] = str(dest)
        INDEX_PATH.write_text(json.dumps(idx, indent=1))
        return dest, False


def cut_segment(src, t_in, t_out, title):
    tag = f"[{int(t_in // 60)}m{t_in % 60:04.1f}s-{int(t_out // 60)}m{t_out % 60:04.1f}s]"
    dest = ensure_downloads() / "trechos" / f"{safe_name(title)} {tag}.wav"
    subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", f"{t_in:.3f}", "-t", f"{t_out - t_in:.3f}", "-i", str(src),
                    "-c:a", "pcm_s24le", str(dest)], check=True)
    return dest


# ───────────────────────── DaVinci Resolve ─────────────────────────
def get_resolve():
    if RESOLVE_MODULES not in sys.path:
        sys.path.append(RESOLVE_MODULES)
    import DaVinciResolveScript as dvr
    return dvr.scriptapp("Resolve")


def tc_to_frames(tc, fps):
    parts = re.split(r"[:;]", tc)
    h, m, s, f = (int(x) for x in parts)
    nom = round(fps)
    frames = (h * 3600 + m * 60 + s) * nom + f
    if ";" in tc:
        drop = 2 if nom <= 30 else 4
        tm = 60 * h + m
        frames -= drop * (tm - tm // 10)
    return frames


def api_status():
    with resolve_lock:
        try:
            r = get_resolve()
        except Exception as e:  # módulo/lib não carregou
            return {"running": False, "error": str(e)}
        if not r:
            return {"running": False}
        proj = r.GetProjectManager().GetCurrentProject()
        tl = proj.GetCurrentTimeline() if proj else None
        return {
            "running": True,
            "project": proj.GetName() if proj else None,
            "timeline": tl.GetName() if tl else None,
            "timecode": tl.GetCurrentTimecode() if tl else None,
            "audioTracks": tl.GetTrackCount("audio") if tl else 0,
        }


def resolve_import(path, to_timeline, track):
    with resolve_lock:
        r = get_resolve()
        if not r:
            raise RuntimeError("DaVinci Resolve não está aberto (ou o scripting externo está desativado).")
        proj = r.GetProjectManager().GetCurrentProject()
        if not proj:
            raise RuntimeError("Abra um projeto no Resolve.")
        mp = proj.GetMediaPool()
        root = mp.GetRootFolder()
        sub = next((f for f in root.GetSubFolderList() if f.GetName() == "Artlist"), None) or mp.AddSubFolder(root, "Artlist")
        mp.SetCurrentFolder(sub)
        items = mp.ImportMedia([str(path)])
        if not items:
            # já existia no pool: procura pelo nome do arquivo
            items = [c for c in sub.GetClipList() if c.GetClipProperty("File Path") == str(path)]
        if not items:
            raise RuntimeError("O Resolve não importou o arquivo.")
        item = items[0]
        if not to_timeline:
            return "Importado no Media Pool (bin “Artlist”)."
        tl = proj.GetCurrentTimeline()
        if not tl:
            raise RuntimeError("Abra uma timeline no Resolve.")
        fps = float(tl.GetSetting("timelineFrameRate"))
        tc_before = tl.GetCurrentTimecode()
        frame = tc_to_frames(tc_before, fps)
        end = frame + max(1, round(audio_duration(path) * fps))

        def busy(n):  # há clipe de áudio sobrepondo [frame, end) na trilha n?
            if n > tl.GetTrackCount("audio"):
                return False
            return any(it.GetStart() < end and it.GetEnd() > frame for it in tl.GetItemListInTrack("audio", n) or [])

        used = track
        while busy(used):  # o Resolve descarta em silêncio inserções que se sobrepõem
            used += 1
            if used > 24:
                raise RuntimeError("Sem trilha de áudio livre nesse ponto.")
        while tl.GetTrackCount("audio") < used:
            tl.AddTrack("audio")
        before = len(tl.GetItemListInTrack("audio", used) or [])
        mp.AppendToTimeline([{"mediaPoolItem": item, "mediaType": 2, "trackIndex": used, "recordFrame": frame}])
        if len(tl.GetItemListInTrack("audio", used) or []) <= before:
            raise RuntimeError("O Resolve não inseriu o clipe (trilha bloqueada?).")
        note = f" (A{track} estava ocupada)" if used != track else ""
        return f"Inserido na trilha A{used} em {tc_before}{note}."


def api_import(body):
    kind = "sfx" if body.get("kind") == "sfx" else "music"
    song_id = str(body.get("songId", ""))
    if not re.fullmatch(r"[\w\-]{1,40}", song_id):
        raise ValueError("songId inválido")
    title = str(body.get("title") or "track")[:120]
    target = body.get("target", "pool")
    track = max(1, min(int(body.get("track") or 1), 24))
    t_in, t_out = body.get("in"), body.get("out")
    src, reused = download_licensed(song_id, kind, title)
    real = audio_duration(src)
    warn = None
    prev = body.get("previewDuration")
    if prev and abs(real - float(prev)) > 1.5:
        warn = (f"A duração do arquivo baixado ({real:.1f}s) difere do preview ({float(prev):.1f}s): "
                "confira o trecho na timeline.")
    path = src
    if t_in is not None and t_out is not None and t_out - t_in > 0.05:
        t_in, t_out = max(0.0, float(t_in)), min(float(t_out), real)
        path = cut_segment(src, t_in, t_out, title)
    msg = resolve_import(path, target == "timeline", track)
    return {"ok": True, "message": msg, "path": str(path), "reusedDownload": reused, "warning": warn}


# ───────────────────────── Diagnóstico ─────────────────────────
def api_doctor():
    """Verifica o que o editor precisa para o app funcionar e diz como corrigir o que faltar."""
    def claude_cli():
        if not CLAUDE:
            return dict(id="claude", ok=False, label="Claude Code CLI",
                        detail="não encontrado",
                        fix="No Terminal: curl -fsSL https://claude.ai/install.sh | bash — depois reinicie o app.")
        v = subprocess.run([CLAUDE, "--version"], capture_output=True, text=True, timeout=30, env=ENV).stdout.strip()
        return dict(id="claude", ok=True, label="Claude Code CLI", detail=v or CLAUDE)

    def login():
        if not CLAUDE:
            return dict(id="login", ok=False, label="Login no Claude", detail="depende do CLI", fix="")
        p = subprocess.run([CLAUDE, "auth", "status"], capture_output=True, text=True, timeout=30, cwd="/tmp", env=ENV)
        try:
            ok = bool(json.loads(p.stdout).get("loggedIn"))
        except ValueError:
            ok = False
        return dict(id="login", ok=ok, label="Login no Claude", detail="conectado" if ok else "sem login",
                    fix="" if ok else "No Terminal rode: claude — e faça login com a sua conta do Claude (Pro/Team).")

    def connector():
        name, status = detect_artlist()
        if not name:
            return dict(id="artlist", ok=False, label="Conector Artlist", detail=status,
                        fix="Em claude.ai → Configurações → Conectores, adicione e conecte o Artlist.")
        ok = "connected" in status.lower() and "needs" not in status.lower()
        if ok:
            ensure_prefix()
        return dict(id="artlist", ok=ok, label="Conector Artlist", detail=f"{name}: {status}",
                    fix="" if ok else "Em claude.ai → Configurações → Conectores, conecte o Artlist (login da sua conta Artlist).")

    def ffmpeg():
        ok = bool(find_bin("ffmpeg")) and bool(find_bin("ffprobe"))
        return dict(id="ffmpeg", ok=ok, label="ffmpeg", detail="ok" if ok else "não encontrado",
                    fix="" if ok else "No Terminal: brew install ffmpeg (ou rode o instalar.command).")

    def resolve():
        s = api_status()
        if s.get("running"):
            return dict(id="resolve", ok=True, label="DaVinci Resolve Studio",
                        detail=f"{s.get('project') or 'sem projeto'} · {s.get('timeline') or 'sem timeline'}")
        is_open = subprocess.run(["pgrep", "-x", "Resolve"], capture_output=True).returncode == 0
        if is_open:
            return dict(id="resolve", ok=False, label="DaVinci Resolve Studio", detail="aberto, mas o script externo está desligado",
                        fix="No Resolve: Preferências → Sistema → Geral → “Uso de script externo” = Local. Reinicie o Resolve.")
        return dict(id="resolve", ok=False, label="DaVinci Resolve Studio", detail="fechado",
                    fix="Abra o DaVinci Resolve Studio com um projeto (a busca funciona sem ele, a importação não).")

    with ThreadPoolExecutor(5) as ex:
        futs = [ex.submit(f) for f in (claude_cli, login, connector, ffmpeg, resolve)]
        checks = []
        for f in futs:
            try:
                checks.append(f.result())
            except Exception as e:
                checks.append(dict(id="erro", ok=False, label="Verificação", detail=str(e), fix=""))
    return {"checks": checks, "ok": all(c["ok"] for c in checks), "downloads": str(get_downloads())}


# ───────────────────────── Configuração (pasta de downloads) ─────────────────────────
def api_get_config():
    d = get_downloads()
    return {"downloads": str(d), "default": str(DEFAULT_DOWNLOADS), "isDefault": d == DEFAULT_DOWNLOADS,
            "exists": d.is_dir()}


def api_set_config(body):
    raw = str(body.get("downloads") or "").strip()
    if not raw:  # vazio = volta ao padrão
        cfg = load_config()
        cfg.pop("downloads", None)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=1))
        return api_get_config()
    p = Path(raw).expanduser()
    if not p.is_absolute():
        raise ValueError("Informe um caminho completo (começando com / ou ~).")
    p = Path(os.path.realpath(p))
    home = Path.home()
    ok_root = home in p.parents or (len(p.parts) > 2 and p.parts[1] == "Volumes")
    if not ok_root or p == home or p == Path("/Volumes"):
        raise ValueError("Escolha uma pasta dentro da sua pasta pessoal ou de um disco em /Volumes.")
    try:
        (p / "trechos").mkdir(parents=True, exist_ok=True)
        probe = p / ".artlist-write-test"
        probe.write_text("ok")
        probe.unlink()
    except OSError as e:
        raise ValueError(f"Não consigo gravar nessa pasta: {e.strerror or e}")
    cfg = load_config()
    cfg["downloads"] = str(p)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=1))
    return api_get_config()


def api_choose_folder(_body):
    """Abre o seletor de pastas nativo do macOS (o servidor roda no Mac do próprio editor)."""
    start = get_downloads()
    start = start if start.is_dir() else Path.home()
    start = str(start).replace("\\", "\\\\").replace('"', '\\"')  # vai dentro de uma string do AppleScript
    script = [
        'tell application "System Events"', "activate",
        f'set f to choose folder with prompt "Pasta para salvar os downloads do Artlist" default location (POSIX file "{start}")',
        "POSIX path of f", "end tell",
    ]
    cmd = ["osascript"] + [x for line in script for x in ("-e", line)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        if "-128" in p.stderr:  # usuário cancelou
            return {"cancelled": True}
        raise RuntimeError("Não foi possível abrir o seletor de pastas: " + p.stderr.strip()[:200])
    return {"path": p.stdout.strip().rstrip("/")}


def api_reveal_downloads(_body):
    d = ensure_downloads()
    subprocess.run(["open", str(d)], check=False)
    return {"ok": True}


# ───────────────────────── HTTP ─────────────────────────
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % a))

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _local_only(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            self._json({"error": "forbidden"}, 403)
            return False
        return True

    def do_GET(self):
        if not self._local_only():
            return
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/":
                data = (HERE / "static" / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif u.path == "/api/ping":  # leve: não toca no Resolve (o script do menu usa isto)
                self._json({"ok": True})
            elif u.path == "/api/status":
                self._json(api_status())
            elif u.path == "/api/doctor":
                self._json(api_doctor())
            elif u.path == "/api/config":
                self._json(api_get_config())
            elif u.path == "/api/peaks":
                self._json(api_peaks(q["u"][0]))
            elif u.path == "/api/audio":
                self._audio(cached_audio(q["u"][0]))
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _audio(self, path):
        size = path.stat().st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        code = 200
        if rng and (m := re.match(r"bytes=(\d*)-(\d*)", rng)):
            if m.group(1):
                start = int(m.group(1))
            if m.group(2):
                end = min(int(m.group(2)), size - 1)
            code = 206
        self.send_response(code)
        self.send_header("Content-Type", "audio/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = fh.read(min(65536, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def do_POST(self):
        if not self._local_only():
            return
        # bloqueia CSRF de outras origens
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
            return self._json({"error": "origem não permitida"}, 403)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            fn = {"/api/search": api_search, "/api/suggest": api_suggest, "/api/import": api_import,
                  "/api/config": api_set_config, "/api/choose-folder": api_choose_folder,
                  "/api/reveal-downloads": api_reveal_downloads}.get(self.path)
            if not fn:
                return self._json({"error": "not found"}, 404)
            self._json(fn(body))
        except Exception as e:
            self._json({"error": str(e)}, 500)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Artlist → Resolve em http://127.0.0.1:{PORT}  (downloads em {get_downloads()})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
