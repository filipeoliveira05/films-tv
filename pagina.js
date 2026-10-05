/* A página é gerada uma vez por dia; este script mantém-na certa ao longo do dia.
   Cada emissão traz o início e o fim absolutos (data-start / data-end, em segundos UTC).
   Ao abrir, e de minuto a minuto, recalcula em que secção está cada emissão, o prazo e a "fita",
   e atualiza as contagens. Sem JavaScript a página continua certa à hora a que foi gerada.
   Para testar outra hora: acrescentar ?t=<milissegundos> ao endereço. */
(() => {
  "use strict";
  const WEEK = 7 * 86400e3;
  const DAY = 86400e3;
  const SECTIONS = ["agora", "gravar", "vir"];
  const forced = Number(new URLSearchParams(location.search).get("t"));
  const clock = () => (forced > 0 ? forced : Date.now());

  const state = (a, now) => (a.start > now ? "vir" : a.end > now ? "agora" : a.start + WEEK > now ? "gravar" : null);

  const remaining = (ms) => {
    const mins = Math.max(0, Math.floor(ms / 60000));
    const d = Math.floor(mins / 1440);
    const h = Math.floor((mins % 1440) / 60);
    const m = mins % 60;
    if (d) return `${d}d ${h}h`;
    if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
    return `${m}m`;
  };

  const pct = (left) => Math.round(Math.max(0, Math.min(1, left / WEEK)) * 1000) / 10;

  const span = (cls, text) => {
    const s = document.createElement("span");
    s.className = cls;
    if (text) s.textContent = text;
    return s;
  };

  // guarda os filmes (um "molde" sem emissões) e as emissões que a página trouxe
  const films = new Map();
  const airings = [];
  document.querySelectorAll(".film").forEach((li) => {
    const id = li.dataset.film;
    let f = films.get(id);
    if (!f) {
      const shell = li.cloneNode(true);
      shell.querySelector(".airings").replaceChildren();
      f = { rank: Number(li.dataset.rank), shell, airings: [] };
      films.set(id, f);
    }
    li.querySelectorAll(".airing").forEach((el) => {
      const a = {
        el,
        start: Number(el.dataset.start) * 1000,
        end: Number(el.dataset.end) * 1000,
        until: el.dataset.until,
        endLabel: el.dataset.endLabel,
        state: null,
      };
      f.airings.push(a);
      airings.push(a);
    });
  });
  const ordered = [...films.values()].sort((x, y) => x.rank - y.rank);

  // segunda linha da emissão: fita (para gravar), hora de fim (agora) ou quanto falta (a vir)
  const paint = (a, now) => {
    const el = a.el;
    [...el.children].forEach((c) => {
      if (!c.classList.contains("where")) c.remove();
    });
    el.classList.remove("urgent");
    if (a.state === "gravar") {
      const left = a.start + WEEK - now;
      const track = span("track");
      const fill = document.createElement("i");
      fill.style.width = `${pct(left)}%`;
      track.append(fill);
      el.append(span("bar"));
      el.lastChild.append(track, span("left", `faltam ${remaining(left)}`), span("until", a.until));
      if (left < DAY) el.classList.add("urgent");
    } else if (a.state === "agora") {
      el.append(span("left", `termina às ${a.endLabel}`));
    } else if (a.state === "vir") {
      el.append(span("left", `em ${remaining(a.start - now)}`));
    }
  };

  const render = (now) => {
    airings.forEach((a) => {
      a.state = state(a, now);
      paint(a, now);
    });
    SECTIONS.forEach((sid) => {
      const list = document.querySelector(`#${sid} .films`);
      list.replaceChildren();
      let count = 0;
      ordered.forEach((f) => {
        const mine = f.airings.filter((a) => a.state === sid).sort((x, y) => x.start - y.start);
        if (!mine.length) return;
        const li = f.shell.cloneNode(true);
        li.querySelector(".airings").append(...mine.map((a) => a.el));
        list.append(li);
        count += 1;
      });
      const section = document.getElementById(sid);
      section.querySelector("h2 .count").textContent = count;
      section.querySelector(".empty").hidden = count > 0;
      const link = document.querySelector(`.jump a[href="#${sid}"]`);
      link.querySelector("b").textContent = count;
      if (sid === "agora") {
        section.hidden = count === 0;
        link.hidden = count === 0;
      }
    });
  };

  // de minuto a minuto: se alguma emissão mudou de secção, refaz tudo; senão só atualiza os tempos
  const update = () => {
    const now = clock();
    if (airings.some((a) => state(a, now) !== a.state)) render(now);
    else airings.forEach((a) => paint(a, now));
  };

  render(clock());
  setInterval(update, 60000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) update();
  });
})();
