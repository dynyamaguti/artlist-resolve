// Workflow Integration plugin: abre o dashboard do app Busca Busca Trilhas e SFX numa janela do Resolve.
// A janela só mostra http://127.0.0.1:8765 (servidor local); a busca e a inserção na timeline
// acontecem no servidor (conector Artlist do Claude + scripting do Resolve).
const { app, BrowserWindow, Menu, shell } = require('electron');
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const PLUGIN_ID = 'com.trendsy.artlistsearch';
const PORT = 8765;
const URL_BASE = `http://127.0.0.1:${PORT}`;
const BASE = path.join(os.homedir(), 'Library/Application Support/ArtlistResolve');
const PYTHONS = ['/opt/homebrew/bin/python3', '/usr/local/bin/python3', '/usr/bin/python3'];

// Handshake opcional com o Resolve: fecha o painel quando o Resolve é encerrado.
try {
    const WI = require('./WorkflowIntegration.node');
    if (WI.Initialize(PLUGIN_ID)) WI.RegisterCallback('ResolveQuit', () => app.quit());
} catch (e) {
    console.log('WorkflowIntegration indisponível (ok fora do Resolve):', e.message);
}

function ping() {
    return new Promise((resolve) => {
        const req = http.get(`${URL_BASE}/api/ping`, { timeout: 1500 }, (res) => { res.resume(); resolve(res.statusCode === 200); });
        req.on('error', () => resolve(false));
        req.on('timeout', () => { req.destroy(); resolve(false); });
    });
}

async function ensureServer() {
    if (await ping()) return { ok: true };
    const appDir = path.join(BASE, 'app');
    const py = PYTHONS.find((p) => fs.existsSync(p));
    if (!py || !fs.existsSync(path.join(appDir, 'server.py'))) {
        return { ok: false, msg: 'Instalação não encontrada. Rode o instalar.command de novo.' };
    }
    fs.mkdirSync(BASE, { recursive: true });
    const log = fs.openSync(path.join(BASE, 'server.log'), 'a');
    spawn(py, [path.join(appDir, 'server.py')], { cwd: appDir, detached: true, stdio: ['ignore', log, log] }).unref();
    for (let i = 0; i < 60; i++) {
        if (await ping()) return { ok: true };
        await new Promise((r) => setTimeout(r, 250));
    }
    return { ok: false, msg: `O servidor não respondeu. Veja ${path.join(BASE, 'server.log')}.` };
}

const page = (html) => 'data:text/html;charset=utf-8,' + encodeURIComponent(
    `<body style="font:14px -apple-system,system-ui;background:#141517;color:#e8e9ea;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;padding:24px">${html}</body>`);

let win = null;

async function createWindow() {
    win = new BrowserWindow({
        width: 560, height: 900, minWidth: 420, minHeight: 500,
        title: 'Busca Busca Trilhas e SFX', backgroundColor: '#141517',
        webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false },
    });
    win.setAlwaysOnTop(true, 'floating'); // painel fica por cima do Resolve (menu Janela → Fixar no topo)
    win.on('close', () => app.quit());

    // links externos abrem no navegador, nunca dentro do painel
    win.webContents.setWindowOpenHandler(({ url }) => { if (/^https?:/.test(url)) shell.openExternal(url); return { action: 'deny' }; });
    win.webContents.on('will-navigate', (e, url) => {
        if (!url.startsWith(URL_BASE) && !url.startsWith('data:')) { e.preventDefault(); if (/^https?:/.test(url)) shell.openExternal(url); }
    });

    win.loadURL(page('Iniciando o Artlist…'));
    const s = await ensureServer();
    if (win.isDestroyed()) return;
    if (s.ok) win.loadURL(URL_BASE);
    else win.loadURL(page(`<div><b>Não foi possível abrir o Artlist</b><p style="color:#8b9096">${s.msg}</p></div>`));
}

function buildMenu() {
    Menu.setApplicationMenu(Menu.buildFromTemplate([
        { label: 'Busca Busca Trilhas e SFX', submenu: [{ role: 'about' }, { type: 'separator' }, { role: 'quit' }] },
        { label: 'Editar', submenu: [{ role: 'undo' }, { role: 'redo' }, { type: 'separator' }, { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' }] },
        { label: 'Janela', submenu: [
            { label: 'Fixar no topo', type: 'checkbox', checked: true, click: (i) => win && win.setAlwaysOnTop(i.checked, 'floating') },
            { label: 'Recarregar', accelerator: 'CmdOrCtrl+R', click: () => win && win.loadURL(URL_BASE) },
            { label: 'Abrir no navegador', click: () => shell.openExternal(URL_BASE) },
            { role: 'minimize' },
        ] },
    ]));
}

if (!app.requestSingleInstanceLock()) {
    app.quit();
} else {
    app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
    app.whenReady().then(() => { buildMenu(); createWindow(); });
    app.on('window-all-closed', () => app.quit());
}
