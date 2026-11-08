const test = require("node:test");
const assert = require("node:assert/strict");
const D = require("../../tierlist_duelos.js");

// gerador pseudoaleatório determinista (mulberry32), para os testes não dependerem do acaso
const rng = (semente) => () => {
  semente |= 0; semente = (semente + 0x6d2b79f5) | 0;
  let t = Math.imul(semente ^ (semente >>> 15), 1 | semente);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const ids = (n) => Array.from({ length: n }, (_, i) => `tt${i + 1}`);
// resultados a partir de uma ordem "verdadeira": quem está primeiro ganha
const daOrdem = (ordem) => {
  let r = {};
  for (let i = 0; i < ordem.length; i++) for (let j = i + 1; j < ordem.length; j++) r = D.registar(r, ordem[i], ordem[j], ordem[i]);
  return r;
};

test("chave é simétrica", () => {
  assert.equal(D.chave("tt2", "tt1"), D.chave("tt1", "tt2"));
  assert.equal(D.chave("tt1", "tt2"), "tt1|tt2");
});

test("pares: n(n-1)/2, cada par uma só vez", () => {
  assert.equal(D.pares([]).length, 0);
  assert.equal(D.pares(["tt1"]).length, 0);
  assert.equal(D.pares(ids(2)).length, 1);
  const p = D.pares(ids(12));
  assert.equal(p.length, 66);
  assert.equal(new Set(p.map(([a, b]) => D.chave(a, b))).size, 66);
});

test("ordemDosPares: todos os pares uma só vez e quase nunca o mesmo filme em duelos seguidos", () => {
  const p = D.ordemDosPares(D.pares(ids(10)), rng(7));
  assert.equal(p.length, 45);
  assert.equal(new Set(p.map(([a, b]) => D.chave(a, b))).size, 45);
  let seguidos = 0;
  for (let i = 1; i < p.length; i++) if (p[i].some((x) => p[i - 1].includes(x))) seguidos++;
  assert.ok(seguidos <= 4, `${seguidos} duelos seguidos com um filme repetido`);
});

test("ordemDosPares não depende da ordem de entrada nem muda a lista original", () => {
  const entrada = D.pares(ids(6));
  const copia = JSON.stringify(entrada);
  D.ordemDosPares(entrada, rng(1));
  assert.equal(JSON.stringify(entrada), copia);
});

test("registar guarda o vencedor, é imutável e recusa vencedores inválidos", () => {
  const r0 = {};
  const r1 = D.registar(r0, "tt1", "tt2", "tt2");
  assert.deepEqual(r0, {});
  assert.deepEqual(r1["tt1|tt2"], { geral: "tt2" });
  assert.deepEqual(D.registar(r1, "tt2", "tt1", "tt1")["tt1|tt2"], { geral: "tt1" }); // refazer um duelo substitui
  assert.equal(D.registar(r1, "tt1", "tt2", "=") === D.registar(r1, "tt1", "tt2", "="), false); // cada registo cria um objeto novo
  assert.equal(D.registar(r1, "tt1", "tt2", "tt9"), r1);
  assert.equal(D.registar(r1, "tt1", "tt1", "tt1"), r1);
});

test("remover tira um resultado", () => {
  const r = D.registar({}, "tt1", "tt2", "tt1");
  assert.deepEqual(D.remover(r, "tt2", "tt1"), {});
  assert.equal(D.remover(r, "tt1", "tt3"), r);
});

test("pendentes e progresso contam só os pares do conjunto", () => {
  let r = D.registar({}, "tt1", "tt2", "tt1");
  r = D.registar(r, "tt1", "tt9", "tt9"); // tt9 não está no tier: ignorado
  const conj = ids(3);
  assert.equal(D.pendentes(r, conj).length, 2);
  assert.deepEqual(D.progresso(r, conj), { feitos: 1, total: 3 });
});

test("pontos: soma dos pontos ganhos (Melhor filme só: 5,5 para o vencedor, 2,5 para o outro; empate 4 e 4)", () => {
  let r = D.registar({}, "tt1", "tt2", "tt1");
  r = D.registar(r, "tt1", "tt3", "=");
  assert.deepEqual(D.pontos(r, ids(3)), { tt1: 9.5, tt2: 2.5, tt3: 4 });
});

test("categorias: cinco, pesos 3/2/1/1/1 com total 8, 'geral' primeiro", () => {
  assert.deepEqual(D.CATEGORIAS.map((c) => [c.id, c.nome, c.peso]), [
    ["geral", "Melhor filme", 3], ["opiniao", "Opinião pessoal", 2], ["plot", "Plot", 1], ["acting", "Acting", 1], ["cinema", "Cinematografia", 1]]);
  assert.equal(D.TOTAL, 8);
});

test("avaliar: o exemplo do desenho (A ganha geral+plot+acting, B ganha opinião+cinema) dá A com 6 contra 2 e margem 4", () => {
  const r = D.registar({}, "tt1", "tt2", { geral: "tt1", opiniao: "tt2", plot: "tt1", acting: "tt1", cinema: "tt2" });
  const x = D.avaliar(r, "tt2", "tt1"); // a ordem dos argumentos não conta
  assert.equal(x.vencedor, "tt1");
  assert.equal(x.pontos.tt1, 5);
  assert.equal(x.pontos.tt2, 3);
  assert.equal(x.margem, 2);
});

test("avaliar: só 'geral' dá margem 3; categorias em falta contam como empate; empate total dá margem 0", () => {
  const r = D.registar({}, "tt1", "tt2", { geral: "tt2" });
  const x = D.avaliar(r, "tt1", "tt2");
  assert.deepEqual([x.vencedor, x.margem, x.pontos.tt2, x.pontos.tt1], ["tt2", 3, 5.5, 2.5]);
  assert.equal(D.avaliar(D.registar({}, "tt1", "tt2", { geral: "=" }), "tt1", "tt2").margem, 0);
  assert.equal(D.avaliar(D.registar({}, "tt1", "tt2", { geral: "=" }), "tt1", "tt2").vencedor, "=");
  assert.equal(D.avaliar({}, "tt1", "tt2"), null);
});

test("avaliar: o Melhor filme não chega para ganhar se o resto pesar mais (1 contra 4)", () => {
  const r = D.registar({}, "tt1", "tt2", { geral: "tt1", opiniao: "tt2", plot: "tt2", acting: "tt2", cinema: "tt2" });
  const x = D.avaliar(r, "tt1", "tt2");
  assert.equal(x.vencedor, "tt2");
  assert.equal(x.margem, 2);
});

test("avaliar aceita o formato antigo (string) como {geral: vencedor}", () => {
  const x = D.avaliar({ "tt1|tt2": "tt1" }, "tt1", "tt2");
  assert.deepEqual([x.vencedor, x.margem], ["tt1", 3]);
  assert.equal(D.avaliar({ "tt1|tt2": "=" }, "tt1", "tt2").margem, 0);
});

test("registar com categorias: exige 'geral' válido, ignora categorias desconhecidas ou inválidas", () => {
  const r0 = {};
  assert.equal(D.registar(r0, "tt1", "tt2", { opiniao: "tt1" }), r0); // sem geral
  assert.equal(D.registar(r0, "tt1", "tt2", { geral: "tt9" }), r0);
  const r = D.registar(r0, "tt1", "tt2", { geral: "tt1", plot: "tt9", acting: "=", extra: "tt1", cinema: "tt2" });
  assert.deepEqual(r["tt1|tt2"], { geral: "tt1", acting: "=", cinema: "tt2" });
});

test("ordenar: uma contradição de margem pequena é preferida a uma de margem grande", () => {
  // ciclo tt1 > tt2 > tt3 > tt1; tt3 ganha a tt1 por pouco (margem 1), os outros claramente (margem 8)
  let r = D.registar({}, "tt1", "tt2", { geral: "tt1", opiniao: "tt1", plot: "tt1", acting: "tt1", cinema: "tt1" }); // margem 8
  r = D.registar(r, "tt2", "tt3", { geral: "tt2", opiniao: "tt2", plot: "tt2", acting: "tt2", cinema: "tt2" });     // margem 8
  r = D.registar(r, "tt1", "tt3", { geral: "tt3", opiniao: "tt1" });                                              // tt3 ganha por 1 (4,5 contra 3,5)
  const o = D.ordenar(r, ids(3));
  assert.deepEqual(o.ordem, ["tt1", "tt2", "tt3"]); // viola o duelo apertado, não os dois claros
  assert.equal(o.contradicoes.length, 1);
  assert.deepEqual([o.contradicoes[0].vencedor, o.contradicoes[0].perdedor], ["tt3", "tt1"]);
  assert.ok(o.contradicoes[0].margem > 0 && o.contradicoes[0].margem < 8);
});

test("ordenar: as contradições vêm por margem decrescente", () => {
  let r = D.registar({}, "tt1", "tt2", { geral: "tt2" });                                                          // tt2 por 3
  r = D.registar(r, "tt3", "tt4", { geral: "tt4", opiniao: "tt4", plot: "tt4", acting: "tt4", cinema: "tt4" });    // tt4 por 8
  r = D.registar(r, "tt1", "tt3", { geral: "tt1", opiniao: "tt1", plot: "tt1", acting: "tt1", cinema: "tt1" });
  r = D.registar(r, "tt2", "tt4", { geral: "tt2", opiniao: "tt2", plot: "tt2", acting: "tt2", cinema: "tt2" });
  // tt1>tt3, tt4>tt3, tt2>tt4, tt2>tt1: sem ciclos, logo nenhuma contradição
  assert.deepEqual(D.ordenar(r, ids(4)).contradicoes, []);
  // com ciclo: tt1>tt2>tt3>tt1, margens 8, 3 e 5: a menor (3) é a violada
  let c = D.registar({}, "tt1", "tt2", { geral: "tt1", opiniao: "tt1", plot: "tt1", acting: "tt1", cinema: "tt1" });
  c = D.registar(c, "tt2", "tt3", { geral: "tt2" });
  c = D.registar(c, "tt1", "tt3", { geral: "tt3", opiniao: "tt3", plot: "tt3", acting: "tt3" });
  const o = D.ordenar(c, ids(3));
  assert.equal(o.contradicoes.length, 1);
  assert.equal(o.contradicoes[0].margem, 3);
});

test("ordenar: com resultados consistentes devolve a ordem verdadeira, sem contradições", () => {
  const verdadeira = ["tt5", "tt3", "tt1", "tt4", "tt2"];
  const o = D.ordenar(daOrdem(verdadeira), ids(5));
  assert.deepEqual(o.ordem, verdadeira);
  assert.deepEqual(o.contradicoes, []);
});

test("ordenar: um ciclo de três tem uma contradição e o resto fica certo", () => {
  let r = D.registar({}, "tt1", "tt2", "tt1");
  r = D.registar(r, "tt2", "tt3", "tt2");
  r = D.registar(r, "tt3", "tt1", "tt3"); // tt1 > tt2 > tt3 > tt1
  for (const x of ["tt1", "tt2", "tt3"]) r = D.registar(r, x, "tt4", x); // todos ganham ao tt4
  const o = D.ordenar(r, ids(4));
  assert.equal(o.ordem[3], "tt4");
  assert.equal(o.contradicoes.length, 1);
  const c = o.contradicoes[0];
  assert.ok(o.ordem.indexOf(c.vencedor) > o.ordem.indexOf(c.perdedor)); // o vencedor ficou abaixo do perdedor
});

test("ordenar: empates e duelos por fazer não geram contradições", () => {
  let r = D.registar({}, "tt1", "tt2", "=");
  r = D.registar(r, "tt2", "tt3", "tt2");
  const o = D.ordenar(r, ids(4));
  assert.deepEqual(o.contradicoes, []);
  assert.equal(o.ordem.length, 4);
  assert.ok(o.ordem.indexOf("tt2") < o.ordem.indexOf("tt3"));
});

test("ordenar: 0 e 1 filmes", () => {
  assert.deepEqual(D.ordenar({}, []).ordem, []);
  assert.deepEqual(D.ordenar({}, ["tt1"]).ordem, ["tt1"]);
});

test("ordenar é ótimo: iguala o mínimo de contradições da força bruta (n=6, resultados aleatórios)", () => {
  const permutacoes = (a) => (a.length <= 1 ? [a] : a.flatMap((x, i) => permutacoes([...a.slice(0, i), ...a.slice(i + 1)]).map((p) => [x, ...p])));
  const conj = ids(6);
  for (const semente of [1, 2, 3, 4, 5, 6]) {
    const al = rng(semente);
    let r = {};
    const qual = () => { const q = al(); return q < 0.45 ? a_ : q < 0.9 ? b_ : "="; };
    let a_, b_;
    for (const [a, b] of D.pares(conj)) {
      a_ = a; b_ = b;
      r = D.registar(r, a, b, { geral: qual(), opiniao: qual(), plot: qual(), acting: qual(), cinema: qual() });
    }
    const custo = (ordem) => {
      let c = 0;
      for (let i = 0; i < ordem.length; i++) for (let j = i + 1; j < ordem.length; j++) {
        const x = D.avaliar(r, ordem[i], ordem[j]);
        if (x.vencedor === ordem[j]) c += x.margem;
      }
      return c;
    };
    const melhor = Math.min(...permutacoes(conj).map(custo));
    const o = D.ordenar(r, conj);
    assert.equal(o.contradicoes.reduce((s, c) => s + c.margem, 0), melhor, `semente ${semente}`);
    assert.equal(custo(o.ordem), melhor);
  }
});

test("ordenar é determinista: os mesmos resultados dão sempre a mesma ordem, mesmo com ciclos", () => {
  let r = D.registar({}, "tt1", "tt2", "tt1");
  r = D.registar(r, "tt2", "tt3", "tt2");
  r = D.registar(r, "tt3", "tt1", "tt3");
  for (const x of ["tt1", "tt2", "tt3"]) r = D.registar(r, x, "tt4", x);
  const a = D.ordenar(r, ids(4)), b = D.ordenar(r, ids(4));
  assert.deepEqual(a, b);
  assert.deepEqual(D.ordenar(r, ["tt4", "tt3", "tt2", "tt1"]).ordem.length, 4);
});

test("ordenar: com mais de 18 filmes (caminho aproximado) devolve uma permutação válida e acerta quando é consistente", () => {
  const grande = ids(24);
  const verdadeira = [...grande].reverse();
  const o = D.ordenar(daOrdem(verdadeira), grande);
  assert.deepEqual(o.ordem, verdadeira);
  assert.deepEqual(o.contradicoes, []);
  const al = rng(9);
  let r = {};
  for (const [a, b] of D.pares(grande)) r = D.registar(r, a, b, al() < 0.5 ? a : b);
  const aleatorio = D.ordenar(r, grande);
  assert.deepEqual([...aleatorio.ordem].sort(), [...grande].sort());
});

test("normalizar higieniza o que vem do armazenamento", () => {
  const sujo = JSON.parse(`{"v":1,"res":{
    "tt1|tt2":"tt2", "tt2|tt3":"=", "tt3|tt4":"tt9", "tt5|tt4":"tt4", "__proto__":"tt1", "tt1|tt1":"tt1",
    "lixo":"x", "tt7|tt8":42, "tt10|tt9":"tt10"}}`);
  const r = D.normalizar(sujo);
  assert.deepEqual(Object.keys(r.res).sort(), ["tt10|tt9", "tt1|tt2", "tt2|tt3"]);
  assert.deepEqual(r.res["tt1|tt2"], { geral: "tt2" }); // formato antigo vira {geral}
  assert.equal(Object.getPrototypeOf(r.res), Object.prototype);
  const novo = D.normalizar({ v: 1, res: { "tt1|tt2": { geral: "tt1", plot: "tt2", acting: "tt9", opiniao: 3 }, "tt3|tt4": { plot: "tt3" }, "tt5|tt6": [] } });
  assert.deepEqual(novo.res, { "tt1|tt2": { geral: "tt1", plot: "tt2" } });
  assert.deepEqual(D.normalizar(null), { v: 1, res: {} });
  assert.deepEqual(D.normalizar({ v: 2, res: { "tt1|tt2": "tt1" } }), { v: 1, res: {} });
});

test("juntar: une os resultados e, no mesmo par, vale o segundo; não muta nenhum", () => {
  const a = D.registar(D.registar({}, "tt1", "tt2", "tt1"), "tt1", "tt3", "tt3");
  const b = D.registar(D.registar({}, "tt1", "tt2", "tt2"), "tt2", "tt3", "=");
  const antesA = JSON.stringify(a), antesB = JSON.stringify(b);
  const j = D.juntar(a, b);
  assert.deepEqual(j, { "tt1|tt2": { geral: "tt2" }, "tt1|tt3": { geral: "tt3" }, "tt2|tt3": { geral: "=" } });
  assert.equal(JSON.stringify(a), antesA);
  assert.equal(JSON.stringify(b), antesB);
});

test("juntar com um dos lados vazio devolve o outro e aguenta valores em falta", () => {
  const a = D.registar({}, "tt1", "tt2", "tt1");
  assert.deepEqual(D.juntar(a, {}), a);
  assert.deepEqual(D.juntar({}, a), a);
  assert.deepEqual(D.juntar(undefined, a), a);
  assert.deepEqual(D.juntar(a, null), a);
});

test("desempenho: 18 filmes com duelos por categorias ordenam-se em tempo útil", () => {
  const conj = ids(18);
  const al = rng(5);
  let r = {};
  for (const [a, b] of D.pares(conj)) r = D.registar(r, a, b, { geral: al() < 0.5 ? a : b, opiniao: al() < 0.5 ? a : b, plot: "=", acting: al() < 0.5 ? a : b });
  const t0 = Date.now();
  const o = D.ordenar(r, conj);
  assert.equal(o.ordem.length, 18);
  assert.ok(Date.now() - t0 < 5000, `demorou ${Date.now() - t0} ms`);
});
