// Gestos de toque REAIS (via Chrome DevTools Protocol) sobre a página da tierlist, sem dependências.
// O Input.dispatchTouchEvent passa pelo compositor, por isso o scroll nativo e o touch-action contam como no telemóvel.
// Uso: node tools/_toque.mjs <pagina.html> <idA> <idB>      (imprime um JSON com o resultado)
import { spawn } from "node:child_process";
import { mkdtempSync, readdirSync } from "node:fs";
import { tmpdir, homedir } from "node:os";
import { join } from "node:path";

const [, , ficheiro, A, B] = process.argv;
const base = join(homedir(), ".cache/ms-playwright");
const pasta = readdirSync(base).filter((d) => d.startsWith("chromium_headless_shell-")).sort().pop();
const sub = readdirSync(join(base, pasta)).find((d) => d.startsWith("chrome-"));
const exe = join(base, pasta, sub, "chrome-headless-shell");
const PORTA = 9300 + Math.floor(Math.random() * 500);
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(exe, ["--no-sandbox", "--disable-gpu", `--remote-debugging-port=${PORTA}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "toque-"))}`, "about:blank"], { stdio: "ignore" });
const fim = (codigo) => { chrome.kill(); process.exit(codigo); };
setTimeout(() => { console.error("tempo esgotado"); fim(2); }, 90000);

let alvo;
for (let i = 0; i < 50 && !alvo; i++) {
  try {
    const lista = await (await fetch(`http://127.0.0.1:${PORTA}/json/list`)).json();
    alvo = lista.find((t) => t.type === "page");
  } catch (e) { /* ainda a arrancar */ }
  if (!alvo) await esperar(200);
}
const ws = new WebSocket(alvo.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let n = 0;
const pendentes = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pendentes.has(d.id)) { pendentes.get(d.id)(d); pendentes.delete(d.id); } };
const enviar = (method, params = {}) => new Promise((r) => { const id = ++n; pendentes.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
const avaliar = async (expr) => {
  const r = await enviar("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
  return r.result.result.value;
};
const toque = (tipo, x, y) => enviar("Input.dispatchTouchEvent", { type: tipo, touchPoints: tipo === "touchEnd" ? [] : [{ x, y, id: 1 }] });

await enviar("Page.enable");
await enviar("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await enviar("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });
await enviar("Page.navigate", { url: `file://${ficheiro}?v=tierlist` });
await esperar(2500);

// prepara: A no tier t2, B no tier t1
await avaliar(`(async () => { window.FilmesTV.marcarVisto('${A}', '${B}'); await new Promise(r => setTimeout(r, 100));
  window.FilmesTV.tierlist.soltar('${A}', 't2', 0); window.FilmesTV.tierlist.soltar('${B}', 't1', 0);
  window.__ctx = []; window.addEventListener('contextmenu', (e) => window.__ctx.push({ alvo: e.target.tagName, evitado: e.defaultPrevented }));
  window.scrollTo(0, 0); })()`);
await esperar(300);

const centro = (sel) => avaliar(`(() => { const r = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2, h: r.height, esq: r.x }; })()`);
const estado = () => avaliar(`JSON.stringify({ t1: window.FilmesTV.tierlist.estado().itens, scroll: window.scrollY, doc: document.documentElement.scrollHeight, ctx: window.__ctx })`).then(JSON.parse);

// 1) arrastar A (tier t2) para o tier t1 com press longo + movimento
const de = await centro(`#tl-tiers .tl-card[data-film="${A}"]`);
const para = await centro(`#tl-tiers .tl-lista[data-tier="t1"]`);
await toque("touchStart", de.x, de.y);
await esperar(450); // press longo
for (let i = 1; i <= 14; i++) { await toque("touchMove", de.x + ((para.esq + 14 - de.x) * i) / 14, de.y + ((para.y - de.y) * i) / 14); await esperar(40); }
await esperar(300);
await toque("touchEnd");
await esperar(500);
const arrasto = await estado();

// 2) mover o dedo logo no início, na vertical, tem de fazer scroll normal (o press longo não pode roubar o scroll)
await avaliar("window.scrollTo(0, 0)");
const c3 = await centro(`#tl-tiers .tl-card[data-film="${B}"]`);
await toque("touchStart", c3.x, c3.y + 60);
for (let i = 1; i <= 10; i++) { await toque("touchMove", c3.x, c3.y + 60 - i * 25); await esperar(16); }
await toque("touchEnd");
await esperar(600);
const rolagem = await estado();

console.log(JSON.stringify({ arrasto, rolagem }));
fim(0);
