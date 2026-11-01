// Screenshot a page after running a bit of JS (clicks, scrolling) via the Chrome DevTools Protocol.
// Usage: node tools/shot_cdp.mjs URL OUT.png WIDTH HEIGHT "js to run after load"
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
const [url, out, w = '1440', h = '1000', js = ''] = process.argv.slice(2);
const port = 9333 + Math.floor(Math.random() * 500);
const chrome = spawn('google-chrome', ['--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(tmpdir() + '/cdp-')}`, `--window-size=${w},${h}`, 'about:blank'],
  { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let tabs;
for (let i = 0; i < 50 && !tabs; i++) { await sleep(200); try { tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); } catch {} }
const ws = new WebSocket(tabs.find(t => t.type === 'page').webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pend = {};
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend[m.id]) { pend[m.id](m.result); delete pend[m.id]; } };
const send = (method, params = {}) => new Promise(r => { pend[++id] = r; ws.send(JSON.stringify({ id, method, params })); });
await send('Emulation.setDeviceMetricsOverride', { width: +w, height: +h, deviceScaleFactor: 1, mobile: false });
await send('Page.enable'); await send('Page.navigate', { url }); await sleep(2500);
if (js) { const r = await send('Runtime.evaluate', { expression: js, awaitPromise: true, returnByValue: true }); if (r?.result?.value !== undefined) console.log(r.result.value); await sleep(800); }
const shot = await send('Page.captureScreenshot', { format: 'png' });
writeFileSync(out, Buffer.from(shot.data, 'base64'));
ws.close(); chrome.kill();
