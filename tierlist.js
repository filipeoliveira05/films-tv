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
    if (editando) {
      const nome = el("input", "tl-nome");
      nome.value = t.nome;
      nome.maxLength = 24;
      nome.setAttribute("aria-label", "Nome do tier");
      const cores = el("div", "tl-cores");
      T.PALETA.forEach((cor) => {
        const b = botao("tl-cor", "", `Cor ${cor}`);
        b.style.background = cor;
        b.dataset.cor = cor;
        b.setAttribute("aria-pressed", String(cor === t.cor));
        cores.append(b);
      });
      label.append(botao("tl-grip", "⋮⋮", "Arrastar o tier"), nome, cores, botao("tl-del", "×", `Apagar o tier ${t.nome}`));
    } else {
      label.textContent = t.nome;
    }
    const lista = el("div", "tl-lista");
    lista.dataset.tier = t.id;
    lista.append(...T.listar(estado, t.id).map((id) => cartao(id, true)));
    row.append(label, lista);
    return row;
  };

  let sortables = [];

  // um só caminho para rato e dedo: forceFallback usa eventos de ponteiro e não o drag and drop nativo (que não
  // funciona com toque); com o dedo é preciso um press longo (delay), para não colidir com o scroll
  const ARRASTO = {
    group: "tl",
    animation: 150,
    forceFallback: true,
    fallbackOnBody: true,
    delay: 220,
    delayOnTouchOnly: true,
    touchStartThreshold: 6,
    draggable: ".tl-card",
    filter: ".tl-x",
    preventOnFilter: false,
    ghostClass: "tl-fantasma",
    fallbackClass: "tl-arrastado",
  };

  const ativarArrasto = () => {
    sortables.forEach((s) => s.destroy());
    sortables = [];
    root.querySelectorAll(".tl-lista").forEach((lista) => {
      const livres = lista.id === "tl-livres";
      sortables.push(
        Sortable.create(lista, {
          ...ARRASTO,
          sort: !livres, // "por classificar" não tem ordem própria
          onEnd: (evt) => {
            if (livres && evt.from === evt.to) return;
            const id = evt.item.dataset.film;
            const tier = evt.to.dataset.tier || null;
            setTimeout(() => soltar(id, tier, evt.newIndex), 0); // deixa o Sortable acabar antes de repintar
          },
        })
      );
    });
    sortables.push(
      Sortable.create($("#tl-tiers"), {
        group: "tiers",
        animation: 150,
        forceFallback: true,
        fallbackOnBody: true,
        handle: ".tl-grip",
        draggable: ".tl-tier",
        delay: 150,
        delayOnTouchOnly: true,
        onEnd: (evt) => setTimeout(() => soltarTier(evt.item.dataset.tier, evt.newIndex), 0),
      })
    );
  };

  function pintar() {
    $("#tl-tiers").replaceChildren(...estado.tiers.map(linha));
    const livres = $("#tl-livres");
    livres.replaceChildren(...T.naoClassificados(estado, FT.vistos()).map((id) => cartao(id, false)));
    $("#tl-vazio").hidden = livres.children.length > 0;
    root.classList.toggle("editando", editando);
    $("#tl-editar").setAttribute("aria-pressed", String(editando));
    $("#tl-novo-tier").hidden = !editando;
    avisar();
    ativarArrasto();
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

  const soltarTier = (id, idx) => {
    if (!mudar(T.moverTier(estado, id, idx))) pintar();
  };

  // ---- pesquisa no TMDB: a chave é do utilizador e fica só neste browser (nunca no código nem no repo)
  const KEY_TMDB = "filmes-tv:tmdb-chave";
  const API = "https://api.themoviedb.org/3";
  const IMG = "https://image.tmdb.org/t/p/w185";
  let chaveMem = ""; // se o armazenamento estiver bloqueado, vale enquanto a página está aberta

  const chave = () => {
    try {
      return localStorage.getItem(KEY_TMDB) || chaveMem;
    } catch (e) {
      return chaveMem;
    }
  };
  const guardarChave = (valor) => {
    chaveMem = valor;
    try {
      if (valor) localStorage.setItem(KEY_TMDB, valor);
      else localStorage.removeItem(KEY_TMDB);
    } catch (e) {
      /* fica só em memória */
    }
  };

  const mensagem = (texto) => {
    const m = $("#tl-msg");
    m.textContent = texto || "";
    m.hidden = !texto;
  };
  const pedirChave = () => {
    $("#tl-chave").hidden = false;
    mensagem("");
    $("#tl-resultados").replaceChildren();
  };

  class SemChave extends Error {}

  const obter = async (caminho, params = {}) => {
    const qs = new URLSearchParams({ api_key: chave(), ...params });
    const r = await fetch(`${API}${caminho}?${qs}`);
    if (r.status === 401) {
      guardarChave("");
      pedirChave();
      throw new SemChave();
    }
    if (!r.ok) throw new Error(`TMDB ${r.status}`);
    return r.json();
  };

  const falha = (e) => {
    if (!(e instanceof SemChave)) mensagem("Sem ligação ao TMDB. Tenta outra vez dentro de pouco tempo.");
  };

  let resultados = [];
  let pedido = 0; // ignora respostas de pesquisas já ultrapassadas

  const procurar = async (q) => {
    const meu = ++pedido;
    if (!q.trim()) {
      resultados = [];
      $("#tl-resultados").replaceChildren();
      return mensagem("");
    }
    if (!chave()) return pedirChave();
    try {
      const d = await obter("/search/movie", { language: "pt-PT", include_adult: "false", query: q.trim() });
      if (meu !== pedido) return;
      resultados = (d.results || []).slice(0, 8);
      mensagem(resultados.length ? "" : "Nenhum filme encontrado.");
      $("#tl-resultados").replaceChildren(
        ...resultados.map((r, i) => {
          const li = el("li");
          const b = botao("tl-res");
          b.dataset.i = i;
          if (r.poster_path) {
            const img = new Image();
            img.src = IMG + r.poster_path;
            img.alt = "";
            img.width = 46;
            img.height = 69;
            b.append(img);
          }
          b.append(el("span", "", `${r.title}${r.release_date ? ` (${r.release_date.slice(0, 4)})` : ""}`));
          li.append(b);
          return li;
        })
      );
    } catch (e) {
      falha(e);
    }
  };

  const escolher = async (r) => {
    try {
      const d = await obter(`/movie/${r.id}/external_ids`);
      if (!d.imdb_id) return mensagem("Este filme não tem ID do IMDb no TMDB: não dá para o adicionar.");
      if (T.contem(estado, d.imdb_id, FT.vistos())) return mensagem(`"${r.title}" já está na tierlist.`);
      const meta = {
        titulo: r.title,
        ano: r.release_date ? r.release_date.slice(0, 4) : null,
        poster: r.poster_path ? IMG + r.poster_path : null,
      };
      mudar(T.adicionar(estado, d.imdb_id, meta));
      FT.marcarVisto(d.imdb_id); // um filme na tierlist conta como visto
      mensagem("");
      $("#tl-q").value = "";
      $("#tl-resultados").replaceChildren();
    } catch (e) {
      falha(e);
    }
  };

  // tocar num cartão de um tier mostra o ✕ nele (o hover não existe no telemóvel); tocar noutro sítio esconde-o.
  // A seleção é só visual: não entra no estado e perde-se quando a vista se repinta.
  const selecionar = (card) => {
    root.querySelectorAll(".tl-sel").forEach((c) => c.classList.remove("tl-sel"));
    if (card) card.classList.add("tl-sel");
  };
  document.addEventListener("click", (e) => {
    if (!root.contains(e.target)) selecionar(null);
  });

  root.addEventListener("click", (e) => {
    const x = e.target.closest(".tl-x");
    if (!x) {
      const card = e.target.closest(".tl-card");
      selecionar(card && card.querySelector(".tl-x") && !card.classList.contains("tl-sel") ? card : null);
    }
    if (x) return soltar(x.closest(".tl-card").dataset.film, null);
    const tier = e.target.closest(".tl-tier");
    const cor = e.target.closest(".tl-cor");
    if (cor && tier) return mudar(T.corTier(estado, tier.dataset.tier, cor.dataset.cor));
    const del = e.target.closest(".tl-del");
    if (del && tier) return mudar(T.apagarTier(estado, tier.dataset.tier));
  });
  root.addEventListener("change", (e) => {
    if (e.target.matches(".tl-nome")) {
      const antes = estado;
      if (!mudar(T.renomearTier(estado, e.target.closest(".tl-tier").dataset.tier, e.target.value)) || antes === estado) pintar();
    }
  });
  $("#tl-editar").addEventListener("click", () => { editando = !editando; pintar(); });
  $("#tl-novo-tier").addEventListener("click", () => mudar(T.adicionarTier(estado)));

  const exportarFicheiro = () => {
    const blob = new Blob([T.exportar(estado)], { type: "application/json" });
    const a = el("a");
    a.href = URL.createObjectURL(blob);
    a.download = `tierlist-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  // devolve true se a tierlist foi substituída; recusa lixo sem tocar nos dados atuais
  const importarTexto = (texto) => {
    const r = T.importar(texto);
    if (!r.ok) {
      alert(r.erro);
      return false;
    }
    if (!confirm("Importar substitui a tierlist atual. Continuar?")) return false;
    mudar(r.estado);
    FT.marcarVisto(...Object.keys(r.estado.itens)); // um filme na tierlist conta como visto
    return true;
  };

  $("#tl-exportar").addEventListener("click", exportarFicheiro);
  $("#tl-importar").addEventListener("click", () => $("#tl-ficheiro").click());
  $("#tl-ficheiro").addEventListener("change", async (e) => {
    const ficheiro = e.target.files[0];
    e.target.value = "";
    if (ficheiro) importarTexto(await ficheiro.text());
  });

  let timer;
  $("#tl-q").addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => procurar(e.target.value), 350);
  });
  $("#tl-resultados").addEventListener("click", (e) => {
    const b = e.target.closest(".tl-res");
    if (b) escolher(resultados[Number(b.dataset.i)]);
  });
  $("#tl-chave-ok").addEventListener("click", () => {
    const v = $("#tl-chave-input").value.trim();
    if (!v) return;
    guardarChave(v);
    $("#tl-chave-input").value = "";
    $("#tl-chave").hidden = true;
    procurar($("#tl-q").value);
  });

  window.addEventListener("storage", (e) => {
    if (e.key === KEY || e.key === null) {
      estado = ler();
      pintar();
    }
  });

  window.FilmesTV.tierlist = { soltar, soltarTier, importarTexto, estado: () => estado }; // também serve às verificações em tools/

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
