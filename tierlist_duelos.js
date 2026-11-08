/* Duelos entre filmes de um mesmo tier: lógica pura, sem DOM nem armazenamento (testada em tests/js/).
   Resultados: {v:1, res:{"ttA|ttB": {geral:id|"=", opiniao:..., plot:..., acting:..., cinema:...}}}, com a chave pelos dois ids
   por ordem alfabética. Só "geral" (Melhor filme) é obrigatório; as outras categorias em falta contam como empate.
   Formato antigo, ainda aceite ao ler: o valor ser só o vencedor ("ttA" | "ttB" | "="), que equivale a {geral: vencedor}.
   Pontuação de um duelo: o vencedor de cada categoria ganha o peso dela, o empate dá metade a cada um; ganha quem tiver mais
   pontos e a margem é a diferença (0 a 8). Um duelo em que só se escolheu o Melhor filme tem margem 3.
   O resultado é de filme contra filme, não de tier: se um filme mudar de tier, os duelos feitos continuam válidos.
   A ordem final minimiza o custo das contradições (duelos em que o vencedor ficou abaixo do perdedor; cada uma custa a sua
   margem): é exata até 18 filmes (programação dinâmica sobre subconjuntos) e aproximada acima disso. O empate não contradiz nada.
   O desempate entre ordens com o mesmo custo usa os pontos totais ganhos. */
const TierDuelos = (() => {
  "use strict";
  const VERSAO = 1;
  const LIMITE_EXATO = 18;
  const K = 1e6; // peso de um ponto de margem frente ao desempate pelos pontos totais (que nunca chega perto)
  // os pesos somam 8; mudar aqui muda a margem de todos os duelos, antigos incluídos
  const CATEGORIAS = [
    { id: "geral", nome: "Melhor filme", peso: 3 },
    { id: "opiniao", nome: "Opinião pessoal", peso: 2 },
    { id: "plot", nome: "Plot", peso: 1 },
    { id: "acting", nome: "Acting", peso: 1 },
    { id: "cinema", nome: "Cinematografia", peso: 1 },
  ];
  const TOTAL = CATEGORIAS.reduce((s, c) => s + c.peso, 0);

  const chave = (a, b) => (a < b ? `${a}|${b}` : `${b}|${a}`);
  const tem = (res, a, b) => Object.prototype.hasOwnProperty.call(res, chave(a, b));

  const pares = (ids) => {
    const r = [];
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) r.push([ids[i], ids[j]]);
    return r;
  };

  // mistura os pares e tenta que dois duelos seguidos não partilhem um filme (melhor esforço, só falha no fim)
  const ordemDosPares = (lista, rand = Math.random) => {
    const resto = lista.map((p) => [...p]);
    for (let i = resto.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      [resto[i], resto[j]] = [resto[j], resto[i]];
    }
    const saida = [];
    while (resto.length) {
      const ant = saida[saida.length - 1];
      let k = ant ? resto.findIndex((p) => !p.some((x) => ant.includes(x))) : 0;
      if (k < 0) k = 0;
      saida.push(resto.splice(k, 1)[0]);
    }
    return saida;
  };

  // o valor de um duelo, limpo: {geral, ...} com vencedores válidos (ids do par ou "="); null se não servir
  const limpar = (valor, a, b) => {
    const ok = (w) => w === a || w === b || w === "=";
    if (typeof valor === "string") return ok(valor) ? { geral: valor } : null;
    if (!valor || typeof valor !== "object" || !ok(valor.geral)) return null;
    const r = { geral: valor.geral };
    for (const c of CATEGORIAS.slice(1)) if (Object.prototype.hasOwnProperty.call(valor, c.id) && ok(valor[c.id])) r[c.id] = valor[c.id];
    return r;
  };

  // `valor` é o vencedor ("ttA" | "ttB" | "=") ou o objeto por categorias
  const registar = (res, a, b, valor) => {
    const v = a === b ? null : limpar(valor, a, b);
    return v ? { ...res, [chave(a, b)]: v } : res;
  };

  // pontuação de um duelo: {vencedor: a | b | "=", margem, pontos: {[a], [b]}} (null se o duelo não existir)
  const avaliar = (res, a, b) => {
    if (!tem(res, a, b)) return null;
    const v = limpar(res[chave(a, b)], a, b);
    if (!v) return null;
    let pa = 0, pb = 0;
    for (const c of CATEGORIAS) {
      const w = Object.prototype.hasOwnProperty.call(v, c.id) ? v[c.id] : "=";
      if (w === a) pa += c.peso; else if (w === b) pb += c.peso; else { pa += c.peso / 2; pb += c.peso / 2; }
    }
    return { vencedor: pa > pb ? a : pb > pa ? b : "=", margem: Math.abs(pa - pb), pontos: { [a]: pa, [b]: pb } };
  };

  const remover = (res, a, b) => {
    if (!tem(res, a, b)) return res;
    const r = { ...res };
    delete r[chave(a, b)];
    return r;
  };

  // junta dois conjuntos de resultados (p. ex. ao importar): no mesmo par vale o segundo
  const juntar = (a, b) => ({ ...(a || {}), ...(b || {}) });

  const pendentes = (res, ids) => pares(ids).filter(([a, b]) => !tem(res, a, b));
  const progresso = (res, ids) => {
    const total = pares(ids).length;
    return { feitos: total - pendentes(res, ids).length, total };
  };

  // pontos totais ganhos nos duelos feitos (só serve de desempate e para mostrar)
  const pontos = (res, ids) => {
    const v = Object.fromEntries(ids.map((id) => [id, 0]));
    for (const [a, b] of pares(ids)) {
      const x = avaliar(res, a, b);
      if (x) { v[a] += x.pontos[a]; v[b] += x.pontos[b]; }
    }
    return v;
  };

  // contradições da ordem, as de maior margem primeiro (e, a igualdade, as mais distantes)
  const contradicoes = (res, ordem) => {
    const lista = [];
    for (let i = 0; i < ordem.length; i++)
      for (let j = i + 1; j < ordem.length; j++) {
        const x = avaliar(res, ordem[i], ordem[j]);
        if (x && x.vencedor === ordem[j]) lista.push({ vencedor: ordem[j], perdedor: ordem[i], margem: x.margem, distancia: j - i });
      }
    return lista.sort((x, y) => y.margem - x.margem || y.distancia - x.distancia).map(({ vencedor, perdedor, margem }) => ({ vencedor, perdedor, margem }));
  };

  const bits = (x) => {
    x -= (x >>> 1) & 0x55555555;
    x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
    return (((x + (x >>> 4)) & 0x0f0f0f0f) * 0x01010101) >>> 24;
  };

  const exata = (res, ids, pt) => {
    const n = ids.length;
    // custo de pôr x abaixo dos de `mask`: soma das margens dos que x venceu. Duas tabelas de 9 bits por filme dão O(1) por passo
    const BAIXO = 9, MAS = (1 << BAIXO) - 1;
    const tab = ids.map((x, i) => {
      const w = ids.map((y, j) => {
        const a = j === i ? null : avaliar(res, x, y);
        return a && a.vencedor === x ? a.margem : 0;
      });
      const lo = new Float64Array(1 << BAIXO), hi = new Float64Array(1 << Math.max(0, n - BAIXO));
      for (let m = 1; m < lo.length; m++) { const b = 31 - Math.clz32(m & -m); lo[m] = lo[m & (m - 1)] + (b < n ? w[b] : 0); }
      for (let m = 1; m < hi.length; m++) { const b = 31 - Math.clz32(m & -m) + BAIXO; hi[m] = hi[m & (m - 1)] + (b < n ? w[b] : 0); }
      return { lo, hi };
    });
    const N = 1 << n;
    const custo = new Float64Array(N).fill(Infinity);
    const pai = new Int8Array(N).fill(-1);
    custo[0] = 0;
    for (let mask = 0; mask < N; mask++) {
      if (custo[mask] === Infinity) continue;
      const pos = bits(mask);
      for (let x = 0; x < n; x++) {
        if (mask & (1 << x)) continue;
        const c = custo[mask] + (tab[x].lo[mask & MAS] + tab[x].hi[mask >>> BAIXO]) * K + pos * pt[ids[x]];
        const nm = mask | (1 << x);
        if (c < custo[nm]) { custo[nm] = c; pai[nm] = x; }
      }
    }
    const ordem = [];
    for (let mask = N - 1; mask; mask ^= 1 << pai[mask]) ordem.push(ids[pai[mask]]);
    return ordem.reverse();
  };

  // acima do limite: parte da ordem por pontos e vai trocando vizinhos enquanto isso reduzir as contradições
  const aproximada = (res, ids, pt) => {
    const ordem = [...ids].sort((a, b) => pt[b] - pt[a] || (a < b ? -1 : 1));
    for (let volta = 0, mudou = true; mudou && volta < ids.length * ids.length; volta++) {
      mudou = false;
      for (let i = 0; i + 1 < ordem.length; i++) {
        const x = avaliar(res, ordem[i], ordem[i + 1]);
        if (x && x.vencedor === ordem[i + 1]) {
          [ordem[i], ordem[i + 1]] = [ordem[i + 1], ordem[i]];
          mudou = true;
        }
      }
    }
    return ordem;
  };

  const ordenar = (res, ids) => {
    const pt = pontos(res, ids);
    if (ids.length <= 1) return { ordem: [...ids], contradicoes: [], pontos: pt };
    const ordem = ids.length <= LIMITE_EXATO ? exata(res, ids, pt) : aproximada(res, ids, pt);
    return { ordem, contradicoes: contradicoes(res, ordem), pontos: pt };
  };

  // o que vem do armazenamento: só chaves bem formadas (ids por ordem alfabética) e valores que fazem sentido no par
  const normalizar = (raw) => {
    const r = { v: VERSAO, res: {} };
    if (!raw || typeof raw !== "object" || raw.v !== VERSAO || !raw.res || typeof raw.res !== "object") return r;
    for (const k of Object.keys(raw.res)) {
      const m = /^(tt\d+)\|(tt\d+)$/.exec(k);
      if (!m || m[1] >= m[2]) continue;
      const v = limpar(raw.res[k], m[1], m[2]);
      if (v) r.res[k] = v;
    }
    return r;
  };

  return { CATEGORIAS, TOTAL, chave, pares, ordemDosPares, registar, avaliar, remover, juntar, pendentes, progresso, pontos, ordenar, normalizar };
})();

if (typeof module !== "undefined") module.exports = TierDuelos;
