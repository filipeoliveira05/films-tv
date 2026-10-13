/* Vista "Tierlist": o estado vive em tierlist_estado.js (TierEstado) e guarda-se em localStorage.
   Usa a ponte window.FilmesTV de pagina.js para ler os vistos. Para testar: ?v=tierlist abre já nesta vista. */
(() => {
  "use strict";
  const FT = window.FilmesTV;
  const root = document.getElementById("main-tier");
  if (!FT || !root) return;

  const KEY = "filmes-tv:tierlist";

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
  vista(new URLSearchParams(location.search).get("v") === "tierlist" ? "tier" : "tv");
})();
