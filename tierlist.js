/* Vista "Tierlist": o estado vive em tierlist_estado.js (TierEstado) e guarda-se em localStorage.
   Usa a ponte window.FilmesTV de pagina.js para ler os vistos. Para testar: ?v=tierlist abre já nesta vista. */
(() => {
  "use strict";
  const FT = window.FilmesTV;
  const T = TierEstado;
  const root = document.getElementById("main-tier");
  if (!FT || !root) return;

  const KEY = "filmes-tv:tierlist";
  const $ = (sel, r = root) => r.querySelector(sel);
  const el = (tag, cls, texto) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (texto !== undefined) e.textContent = texto;
    return e;
  };
  const botao = (cls, texto, rotulo) => {
    const b = el("button", cls, texto);
    b.type = "button";
    if (rotulo) b.setAttribute("aria-label", rotulo);
    return b;
  };

  let estado = T.novo();
  let editando = false;
  let guardavel = true; // false se o armazenamento está bloqueado (modo privado): vale só nesta sessão

  const ler = () => {
    let raw = null;
    try {
      raw = localStorage.getItem(KEY);
    } catch (e) {
      guardavel = false;
    }
    if (!raw) return T.novo();
    try {
      return T.normalizar(JSON.parse(raw)) || T.novo();
    } catch (e) {
      return T.novo(); // valor corrompido: recomeça com os tiers por omissão
    }
  };

  const avisar = () => { $("#tl-aviso").hidden = guardavel; };

  const gravar = () => {
    try {
      localStorage.setItem(KEY, JSON.stringify(estado));
    } catch (e) {
      guardavel = false;
    }
    avisar();
  };

  const mudar = (novo) => {
    if (novo === estado) return false;
    estado = novo;
    gravar();
    pintar();
    return true;
  };

  // cartão de um filme: poster (ou o título, se não há poster) e, dentro de um tier, o ✕ que o devolve a "por classificar"
  const cartao = (id, comX) => {
    const m = estado.filmes[id];
    const c = el("div", "tl-card");
    c.dataset.film = id;
    c.title = m.titulo + (m.ano ? ` (${m.ano})` : "");
    if (m.poster) {
      const img = new Image();
      img.src = m.poster;
      img.alt = "";
      img.width = 185;
      img.height = 278;
      img.loading = "lazy";
      img.draggable = false;
      c.append(img);
    } else {
      c.append(el("span", "tl-sem", m.titulo));
    }
    if (comX) c.append(botao("tl-x", "×", `Tirar ${m.titulo} do tier`));
    return c;
  };

  const linha = (t) => {
    const row = el("div", "tl-tier");
    row.dataset.tier = t.id;
    const label = el("div", "tl-label");
    label.style.background = t.cor;
    label.textContent = t.nome;
    const lista = el("div", "tl-lista");
    lista.dataset.tier = t.id;
    lista.append(...T.listar(estado, t.id).map((id) => cartao(id, true)));
    row.append(label, lista);
    return row;
  };

  function pintar() {
    $("#tl-tiers").replaceChildren(...estado.tiers.map(linha));
    const livres = $("#tl-livres");
    livres.replaceChildren(...T.naoClassificados(estado, FT.vistos()).map((id) => cartao(id, false)));
    $("#tl-vazio").hidden = livres.children.length > 0;
    avisar();
  }

  // guarda na tierlist os metadados dos vistos que a grelha conhece (para sobreviverem quando saírem da grelha)
  const sincronizar = () => {
    let s = estado;
    FT.vistos().forEach((id) => {
      const m = FT.metaFilme(id);
      if (m) s = T.guardarMeta(s, id, m);
    });
    if (s !== estado) {
      estado = s;
      gravar();
    }
    pintar();
  };

  // largar um filme num tier (ou em "por classificar", com tier null)
  const soltar = (id, tier, idx) => {
    if (!mudar(T.mover(estado, id, tier, idx))) pintar();
  };

  root.addEventListener("click", (e) => {
    const x = e.target.closest(".tl-x");
    if (x) soltar(x.closest(".tl-card").dataset.film, null);
  });

  window.addEventListener("storage", (e) => {
    if (e.key === KEY || e.key === null) {
      estado = ler();
      pintar();
    }
  });

  window.FilmesTV.tierlist = { soltar, estado: () => estado }; // também serve às verificações em tools/

  const vista = (nome) => {
    const tier = nome === "tier";
    document.getElementById("main-tv").hidden = tier;
    root.hidden = !tier;
    document.querySelector(".jump").dataset.vista = nome;
    document.getElementById("v-tv").setAttribute("aria-pressed", String(!tier));
    document.getElementById("v-tier").setAttribute("aria-pressed", String(tier));
    window.scrollTo(0, 0);
  };

  document.getElementById("v-tv").addEventListener("click", () => vista("tv"));
  document.getElementById("v-tier").addEventListener("click", () => vista("tier"));
  document.querySelector(".views").hidden = false; // sem JavaScript o comutador nem aparece

  estado = ler();
  FT.aoMudarMarcas(sincronizar);
  sincronizar();
  vista(new URLSearchParams(location.search).get("v") === "tierlist" ? "tier" : "tv");
})();
