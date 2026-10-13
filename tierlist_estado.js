/* Estado da tierlist pessoal: funções puras, sem DOM nem armazenamento (testadas em tests/js/).
   Estado: {v:1, tiers:[{id,nome,cor}], itens:{<imdb_id>:{tier,pos}}, filmes:{<imdb_id>:{titulo,ano,poster}}}.
   tier === null quer dizer "por classificar". Cada função devolve um estado novo, ou o mesmo objeto se nada mudou. */
const TierEstado = (() => {
  "use strict";
  const VERSAO = 1;
  // sem vermelho nem ouro: são reservados a "gravar" e ao rating
  const PALETA = ["#ff9f43", "#ff7eb6", "#b48cff", "#6fa8ff", "#5ee0e0", "#b8e65a", "#b4bccf", "#8ff0cf"];
  const NOMES = ["S", "A", "B", "C", "D"];
  const MAX_NOME = 24;
  const IMG = "https://image.tmdb.org/t/p/";

  const copia = (s) => JSON.parse(JSON.stringify(s));

  const novo = () => ({
    v: VERSAO,
    tiers: NOMES.map((nome, i) => ({ id: `t${i + 1}`, nome, cor: PALETA[i % PALETA.length] })),
    itens: {},
    filmes: {},
  });

  // ids de um tier (ou de "por classificar" com null), por posição
  const listar = (s, tier) =>
    Object.keys(s.itens)
      .filter((id) => s.itens[id].tier === tier)
      .sort((a, b) => s.itens[a].pos - s.itens[b].pos || (a < b ? -1 : 1));

  const numerar = (s, tier) => listar(s, tier).forEach((id, i) => { s.itens[id].pos = i; });

  const limparMeta = (m) => {
    if (!m || typeof m.titulo !== "string" || !m.titulo.trim()) return null;
    return {
      titulo: m.titulo.trim().slice(0, 200),
      ano: typeof m.ano === "string" && /^\d{4}$/.test(m.ano) ? m.ano : null,
      poster: typeof m.poster === "string" && m.poster.startsWith(IMG) ? m.poster : null,
    };
  };
  const igual = (a, b) => a && b && a.titulo === b.titulo && a.ano === b.ano && a.poster === b.poster;

  const adicionar = (s, id, meta) => {
    const m = limparMeta(meta);
    if (s.itens[id] || !m) return s;
    const r = copia(s);
    const pos = listar(r, null).length;
    r.filmes[id] = m;
    r.itens[id] = { tier: null, pos };
    return r;
  };

  const guardarMeta = (s, id, meta) => {
    const m = limparMeta(meta);
    if (!m || igual(s.filmes[id], m)) return s;
    const r = copia(s);
    r.filmes[id] = m;
    return r;
  };

  const contem = (s, id, vistos) => Boolean(s.itens[id]) || Boolean(vistos && vistos.has(id) && s.filmes[id]);

  // "por classificar": os explícitos (por posição) e depois os vistos conhecidos que nunca foram postos num tier
  const naoClassificados = (s, vistos) => {
    const implicitos = [...vistos]
      .filter((id) => !s.itens[id] && s.filmes[id])
      .sort((a, b) => s.filmes[a].titulo.localeCompare(s.filmes[b].titulo, "pt") || (a < b ? -1 : 1));
    return listar(s, null).concat(implicitos);
  };

  const mover = (s, id, tier, idx) => {
    if (!s.itens[id] && !s.filmes[id]) return s;
    if (tier !== null && !s.tiers.some((t) => t.id === tier)) return s;
    const r = copia(s);
    const antigo = r.itens[id] ? r.itens[id].tier : null;
    r.itens[id] = r.itens[id] || { tier: null, pos: 0 };
    const destino = listar(r, tier).filter((x) => x !== id);
    // "por classificar" não tem ordem própria: entra sempre no fim
    const i = tier === null || idx === undefined ? destino.length : Math.max(0, Math.min(idx, destino.length));
    destino.splice(i, 0, id);
    r.itens[id].tier = tier;
    destino.forEach((x, k) => { r.itens[x].pos = k; });
    numerar(r, antigo);
    return r;
  };

  const remover = (s, id) => mover(s, id, null);

  const novoId = (s) => `t${Math.max(5, ...s.tiers.map((t) => Number(t.id.slice(1)) || 0)) + 1}`;

  const adicionarTier = (s, nome = "Novo") => {
    const r = copia(s);
    r.tiers.push({ id: novoId(s), nome: nome.trim().slice(0, MAX_NOME) || "Novo", cor: PALETA[s.tiers.length % PALETA.length] });
    return r;
  };

  const mudarTier = (s, id, campo, valor) => {
    const i = s.tiers.findIndex((t) => t.id === id);
    if (i < 0 || s.tiers[i][campo] === valor) return s;
    const r = copia(s);
    r.tiers[i][campo] = valor;
    return r;
  };

  const renomearTier = (s, id, nome) => {
    const limpo = String(nome).trim().slice(0, MAX_NOME);
    return limpo ? mudarTier(s, id, "nome", limpo) : s;
  };

  const corTier = (s, id, cor) => (PALETA.includes(cor) ? mudarTier(s, id, "cor", cor) : s);

  const apagarTier = (s, id) => {
    if (!s.tiers.some((t) => t.id === id)) return s;
    let r = copia(s);
    listar(r, id).forEach((f) => { r = mover(r, f, null); });
    r.tiers = r.tiers.filter((t) => t.id !== id);
    return r;
  };

  const moverTier = (s, id, idx) => {
    const i = s.tiers.findIndex((t) => t.id === id);
    if (i < 0) return s;
    const r = copia(s);
    const [t] = r.tiers.splice(i, 1);
    r.tiers.splice(Math.max(0, Math.min(idx, r.tiers.length)), 0, t);
    return r;
  };

  // aceita só o que reconhece; o resto é descartado ou corrigido (vale também para o ficheiro importado)
  const normalizar = (raw) => {
    if (!raw || typeof raw !== "object" || Array.isArray(raw) || raw.v !== VERSAO || !Array.isArray(raw.tiers)) return null;
    const r = { v: VERSAO, tiers: [], itens: {}, filmes: {} };
    const ids = new Set();
    for (const t of raw.tiers) {
      if (!t || typeof t.id !== "string" || !/^t\d+$/.test(t.id) || ids.has(t.id)) continue;
      const nome = String(t.nome == null ? "" : t.nome).trim().slice(0, MAX_NOME);
      if (!nome) continue;
      ids.add(t.id);
      r.tiers.push({ id: t.id, nome, cor: PALETA.includes(t.cor) ? t.cor : PALETA[0] });
    }
    const filmes = raw.filmes && typeof raw.filmes === "object" ? raw.filmes : {};
    for (const id of Object.keys(filmes)) {
      const m = limparMeta(filmes[id]);
      if (m && /^tt\d+$/.test(id)) r.filmes[id] = m;
    }
    const itens = raw.itens && typeof raw.itens === "object" ? raw.itens : {};
    for (const id of Object.keys(itens)) {
      if (!r.filmes[id]) continue;
      const it = itens[id] || {};
      r.itens[id] = { tier: ids.has(it.tier) ? it.tier : null, pos: Number.isFinite(it.pos) ? it.pos : 0 };
    }
    [null, ...r.tiers.map((t) => t.id)].forEach((t) => numerar(r, t));
    return r;
  };

  const exportar = (s) => JSON.stringify(s, null, 1);

  const importar = (texto) => {
    let raw;
    try {
      raw = JSON.parse(texto);
    } catch (e) {
      return { ok: false, erro: "O ficheiro não é JSON válido." };
    }
    const estado = normalizar(raw);
    return estado ? { ok: true, estado } : { ok: false, erro: "O ficheiro não é uma tierlist desta página (versão desconhecida)." };
  };

  return {
    PALETA, novo, normalizar, exportar, importar, listar, naoClassificados, contem,
    adicionar, guardarMeta, mover, remover, adicionarTier, renomearTier, corTier, apagarTier, moverTier,
  };
})();

if (typeof module !== "undefined") module.exports = TierEstado;
