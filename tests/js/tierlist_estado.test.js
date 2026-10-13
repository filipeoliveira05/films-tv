const test = require("node:test");
const assert = require("node:assert/strict");
const T = require("../../tierlist_estado.js");

const M = (titulo, ano = "2000") => ({ titulo, ano, poster: "https://image.tmdb.org/t/p/w185/x.jpg" });
const com = (...filmes) => filmes.reduce((s, [id, t]) => T.adicionar(s, id, M(t)), T.novo());

test("novo: tiers S A B C D com ids t1..t5, cores da paleta e nada dentro", () => {
  const s = T.novo();
  assert.deepEqual(s.tiers.map((t) => t.nome), ["S", "A", "B", "C", "D"]);
  assert.deepEqual(s.tiers.map((t) => t.id), ["t1", "t2", "t3", "t4", "t5"]);
  assert.ok(s.tiers.every((t) => T.PALETA.includes(t.cor)));
  assert.deepEqual(s.itens, {});
  assert.equal(s.v, 1);
});

test("a paleta não tem vermelho nem ouro", () => {
  assert.equal(T.PALETA.length, 8);
  assert.ok(!T.PALETA.includes("#ff4a4a") && !T.PALETA.includes("#ffe066"));
});

test("adicionar põe o filme em 'por classificar' no fim e guarda os metadados", () => {
  const s = com(["tt1", "Um"], ["tt2", "Dois"]);
  assert.deepEqual(T.listar(s, null), ["tt1", "tt2"]);
  assert.equal(s.filmes.tt1.titulo, "Um");
});

test("adicionar um filme que já lá está devolve o mesmo estado", () => {
  const s = com(["tt1", "Um"]);
  assert.equal(T.adicionar(s, "tt1", M("Um")), s);
});

test("adicionar sem título devolve o mesmo estado", () => {
  const s = T.novo();
  assert.equal(T.adicionar(s, "tt1", { titulo: "", ano: null, poster: null }), s);
});

test("não muta o estado original", () => {
  const s = com(["tt1", "Um"]);
  const antes = JSON.stringify(s);
  T.mover(s, "tt1", "t1", 0);
  assert.equal(JSON.stringify(s), antes);
});

test("mover para um tier e reordenar dentro dele", () => {
  let s = com(["tt1", "Um"], ["tt2", "Dois"], ["tt3", "Três"]);
  s = T.mover(s, "tt1", "t1");
  s = T.mover(s, "tt2", "t1");
  s = T.mover(s, "tt3", "t1");
  assert.deepEqual(T.listar(s, "t1"), ["tt1", "tt2", "tt3"]);
  s = T.mover(s, "tt3", "t1", 0);
  assert.deepEqual(T.listar(s, "t1"), ["tt3", "tt1", "tt2"]);
  s = T.mover(s, "tt3", "t1", 99); // índice a mais vai para o fim
  assert.deepEqual(T.listar(s, "t1"), ["tt1", "tt2", "tt3"]);
});

test("mover entre tiers renumera os dois", () => {
  let s = com(["tt1", "Um"], ["tt2", "Dois"]);
  s = T.mover(T.mover(s, "tt1", "t1"), "tt2", "t1");
  s = T.mover(s, "tt1", "t2");
  assert.deepEqual(T.listar(s, "t1"), ["tt2"]);
  assert.equal(s.itens.tt2.pos, 0);
  assert.deepEqual(T.listar(s, "t2"), ["tt1"]);
});

test("mover para um tier inexistente, ou um filme desconhecido, não faz nada", () => {
  const s = com(["tt1", "Um"]);
  assert.equal(T.mover(s, "tt1", "t99", 0), s);
  assert.equal(T.mover(s, "tt9", "t1", 0), s);
});

test("remover devolve o filme a 'por classificar', no fim", () => {
  let s = com(["tt1", "Um"], ["tt2", "Dois"]);
  s = T.mover(s, "tt1", "t1");
  s = T.remover(s, "tt1");
  assert.deepEqual(T.listar(s, "t1"), []);
  assert.deepEqual(T.listar(s, null), ["tt2", "tt1"]);
});

test("naoClassificados junta os explícitos aos vistos conhecidos sem tier, por título", () => {
  let s = com(["tt1", "Zebra"]);
  s = T.guardarMeta(s, "tt2", M("Alfa"));
  s = T.guardarMeta(s, "tt3", M("Beta"));
  s = T.guardarMeta(s, "tt4", M("Gama"));
  s = T.mover(s, "tt4", "t1"); // classificado: sai
  assert.deepEqual(T.naoClassificados(s, new Set(["tt2", "tt3", "tt4"])), ["tt1", "tt2", "tt3"]);
});

test("naoClassificados ignora vistos sem metadados (Review Focus 3)", () => {
  const s = com(["tt1", "Um"]);
  assert.deepEqual(T.naoClassificados(s, new Set(["tt1", "tt77"])), ["tt1"]);
});

test("mover um visto implícito para um tier passa a ser explícito", () => {
  let s = T.guardarMeta(T.novo(), "tt2", M("Alfa"));
  s = T.mover(s, "tt2", "t3", 0);
  assert.deepEqual(T.listar(s, "t3"), ["tt2"]);
});

test("contem: explícito, ou visto implícito com metadados", () => {
  let s = com(["tt1", "Um"]);
  s = T.guardarMeta(s, "tt2", M("Dois"));
  assert.equal(T.contem(s, "tt1"), true);
  assert.equal(T.contem(s, "tt2"), false);
  assert.equal(T.contem(s, "tt2", new Set(["tt2"])), true);
  assert.equal(T.contem(s, "tt3", new Set(["tt3"])), false);
});

test("guardarMeta devolve o mesmo estado se nada mudou", () => {
  const s = T.guardarMeta(T.novo(), "tt1", M("Um"));
  assert.equal(T.guardarMeta(s, "tt1", M("Um")), s);
  assert.notEqual(T.guardarMeta(s, "tt1", M("Um", "2001")), s);
});

test("adicionarTier usa a próxima cor da paleta e um id novo", () => {
  const s = T.adicionarTier(T.novo(), "Obra-prima");
  const t = s.tiers[s.tiers.length - 1];
  assert.equal(t.nome, "Obra-prima");
  assert.equal(t.id, "t6");
  assert.ok(T.PALETA.includes(t.cor));
});

test("adicionarTier não reutiliza ids de tiers apagados", () => {
  let s = T.novo();
  s = T.apagarTier(s, "t5");
  assert.equal(T.adicionarTier(s).tiers.slice(-1)[0].id, "t6");
  s = T.apagarTier(s, "t1");
  assert.equal(T.adicionarTier(s).tiers.slice(-1)[0].id, "t6");
});

test("renomearTier apara espaços, limita a 24 caracteres e recusa vazio", () => {
  const s = T.novo();
  assert.equal(T.renomearTier(s, "t1", "  Top  ").tiers[0].nome, "Top");
  assert.equal(T.renomearTier(s, "t1", "x".repeat(40)).tiers[0].nome.length, 24);
  assert.equal(T.renomearTier(s, "t1", "   "), s);
  assert.equal(T.renomearTier(s, "t99", "Top"), s);
});

test("corTier só aceita cores da paleta", () => {
  const s = T.novo();
  assert.equal(T.corTier(s, "t1", T.PALETA[3]).tiers[0].cor, T.PALETA[3]);
  assert.equal(T.corTier(s, "t1", "#ff0000"), s);
});

test("apagarTier devolve os filmes a 'por classificar' por ordem (Review Focus 4)", () => {
  let s = com(["tt1", "Um"], ["tt2", "Dois"], ["tt3", "Três"]);
  s = T.mover(T.mover(s, "tt1", "t2"), "tt2", "t2");
  s = T.mover(s, "tt3", null);
  s = T.apagarTier(s, "t2");
  assert.ok(!s.tiers.some((t) => t.id === "t2"));
  assert.deepEqual(T.listar(s, null), ["tt3", "tt1", "tt2"]);
});

test("apagar todos os tiers deixa tudo em 'por classificar'", () => {
  let s = T.mover(com(["tt1", "Um"]), "tt1", "t1");
  for (const t of [...s.tiers]) s = T.apagarTier(s, t.id);
  assert.deepEqual(s.tiers, []);
  assert.deepEqual(T.listar(s, null), ["tt1"]);
});

test("moverTier reordena as linhas", () => {
  const s = T.moverTier(T.novo(), "t4", 0);
  assert.deepEqual(s.tiers.map((t) => t.nome), ["C", "S", "A", "B", "D"]);
  assert.deepEqual(T.moverTier(T.novo(), "t1", 99).tiers.map((t) => t.nome), ["A", "B", "C", "D", "S"]);
  assert.equal(T.moverTier(T.novo(), "t99", 0).tiers.length, 5);
});

test("exportar e importar fazem ida e volta", () => {
  let s = com(["tt1", "Um"], ["tt2", "Dois"]);
  s = T.mover(s, "tt1", "t2");
  s = T.renomearTier(s, "t2", "Ótimos");
  const r = T.importar(T.exportar(s));
  assert.equal(r.ok, true);
  assert.deepEqual(r.estado, s);
});

test("importar recusa lixo, versão desconhecida e tipos errados (Review Focus 1)", () => {
  for (const txt of ["", "isto não é json", "null", "[]", "42", '{"v":2,"tiers":[]}', '{"v":1}', '{"v":1,"tiers":"x"}']) {
    const r = T.importar(txt);
    assert.equal(r.ok, false, txt);
    assert.equal(typeof r.erro, "string");
  }
});

test("normalizar higieniza: poster de fora, ids estranhos, __proto__, nomes longos (Review Focus 1)", () => {
  const sujo = JSON.parse(`{
    "v": 1,
    "tiers": [
      {"id": "t1", "nome": "${"x".repeat(100)}", "cor": "#ff0000"},
      {"id": "t1", "nome": "repetido", "cor": "#000000"},
      {"id": "evil", "nome": "x", "cor": "#000000"},
      {"id": "t2", "nome": "   ", "cor": "#000000"},
      {"id": "t3", "nome": "Bom", "cor": "${T.PALETA[2]}"}
    ],
    "itens": {
      "tt1": {"tier": "t3", "pos": 5},
      "tt2": {"tier": "t99", "pos": "a"},
      "tt3": {"tier": "t1", "pos": 0},
      "__proto__": {"tier": "t1", "pos": 0}
    },
    "filmes": {
      "tt1": {"titulo": "Um", "ano": "1999", "poster": "https://evil.example/x.jpg"},
      "tt2": {"titulo": "Dois", "ano": "abcd", "poster": "javascript:alert(1)"},
      "__proto__": {"titulo": "Mau"},
      "ttx": {"titulo": "Mau"}
    }
  }`);
  const s = T.normalizar(sujo);
  assert.deepEqual(s.tiers.map((t) => t.id), ["t1", "t3"]);
  assert.equal(s.tiers[0].nome.length, 24);
  assert.equal(s.tiers[0].cor, T.PALETA[0]); // cor inválida cai na primeira da paleta
  assert.equal(s.filmes.tt1.poster, null);
  assert.equal(s.filmes.tt2.poster, null);
  assert.equal(s.filmes.tt2.ano, null);
  assert.deepEqual(Object.keys(s.filmes).sort(), ["tt1", "tt2"]);
  assert.equal(s.itens.tt1.tier, "t3");
  assert.equal(s.itens.tt2.tier, null); // tier inexistente → por classificar
  assert.ok(!("tt3" in s.itens)); // sem metadados: descartado
  assert.equal(Object.getPrototypeOf(s.filmes), Object.prototype);
});

test("normalizar renumera as posições", () => {
  const s = T.normalizar({
    v: 1,
    tiers: [{ id: "t1", nome: "S", cor: T.PALETA[0] }],
    itens: { tt1: { tier: "t1", pos: 10 }, tt2: { tier: "t1", pos: 3 } },
    filmes: { tt1: { titulo: "Um", ano: null, poster: null }, tt2: { titulo: "Dois", ano: null, poster: null } },
  });
  assert.deepEqual(T.listar(s, "t1"), ["tt2", "tt1"]);
  assert.deepEqual([s.itens.tt2.pos, s.itens.tt1.pos], [0, 1]);
});
