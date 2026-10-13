/* Duelos entre filmes de um mesmo tier: lógica pura, sem DOM nem armazenamento (testada em tests/js/).
   Resultados: {v:1, res:{"ttA|ttB": "ttA" | "ttB" | "="}}, com a chave pelos dois ids por ordem alfabética.
   O resultado é de filme contra filme, não de tier: se um filme mudar de tier, os duelos feitos continuam válidos.
   A ordem final minimiza as contradições (duelos em que o vencedor ficou abaixo do perdedor): é exata até 18 filmes
   (programação dinâmica sobre subconjuntos) e aproximada acima disso. O empate vale meio ponto e não contradiz nada. */
const TierDuelos = (() => {
  "use strict";
  const VERSAO = 1;
  const LIMITE_EXATO = 18;
  const K = 1e6; // peso de uma contradição frente ao desempate por vitórias (que nunca chega perto)

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

  const registar = (res, a, b, vencedor) => {
    if (a === b || (vencedor !== a && vencedor !== b && vencedor !== "=")) return res;
    return { ...res, [chave(a, b)]: vencedor };
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

  // pontos a dobrar para ficarem inteiros: vitória 2, empate 1
  const vitorias = (res, ids) => {
    const v = Object.fromEntries(ids.map((id) => [id, 0]));
    for (const [a, b] of pares(ids)) {
      if (!tem(res, a, b)) continue;
      const w = res[chave(a, b)];
      if (w === "=") { v[a] += 1; v[b] += 1; } else v[w] += 2;
    }
    return v;
  };

  const contradicoes = (res, ordem) => {
    const lista = [];
    for (let i = 0; i < ordem.length; i++)
      for (let j = i + 1; j < ordem.length; j++)
        if (res[chave(ordem[i], ordem[j])] === ordem[j]) lista.push({ vencedor: ordem[j], perdedor: ordem[i], distancia: j - i });
    return lista.sort((x, y) => y.distancia - x.distancia).map(({ vencedor, perdedor }) => ({ vencedor, perdedor }));
  };

  const bits = (x) => {
    x -= (x >>> 1) & 0x55555555;
    x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
    return (((x + (x >>> 4)) & 0x0f0f0f0f) * 0x01010101) >>> 24;
  };

  const exata = (res, ids, pontos) => {
    const n = ids.length;
    const venceu = ids.map((x, i) => ids.reduce((m, y, j) => (j !== i && res[chave(x, y)] === x ? m | (1 << j) : m), 0));
    const N = 1 << n;
    const custo = new Float64Array(N).fill(Infinity);
    const pai = new Int8Array(N).fill(-1);
    custo[0] = 0;
    for (let mask = 0; mask < N; mask++) {
      if (custo[mask] === Infinity) continue;
      const pos = bits(mask);
      for (let x = 0; x < n; x++) {
        if (mask & (1 << x)) continue;
        // x vai para baixo de todos os de `mask`: cada um que x tenha vencido é uma contradição
        const c = custo[mask] + bits(mask & venceu[x]) * K + pos * pontos[ids[x]];
        const nm = mask | (1 << x);
        if (c < custo[nm]) { custo[nm] = c; pai[nm] = x; }
      }
    }
    const ordem = [];
    for (let mask = N - 1; mask; mask ^= 1 << pai[mask]) ordem.push(ids[pai[mask]]);
    return ordem.reverse();
  };

  // acima do limite: parte da ordem por vitórias e vai trocando vizinhos enquanto isso reduzir as contradições
  const aproximada = (res, ids, pontos) => {
    const ordem = [...ids].sort((a, b) => pontos[b] - pontos[a] || (a < b ? -1 : 1));
    for (let volta = 0, mudou = true; mudou && volta < ids.length * ids.length; volta++) {
      mudou = false;
      for (let i = 0; i + 1 < ordem.length; i++) {
        if (res[chave(ordem[i], ordem[i + 1])] === ordem[i + 1]) {
          [ordem[i], ordem[i + 1]] = [ordem[i + 1], ordem[i]];
          mudou = true;
        }
      }
    }
    return ordem;
  };

  const ordenar = (res, ids) => {
    const pontos = vitorias(res, ids);
    if (ids.length <= 1) return { ordem: [...ids], contradicoes: [], vitorias: pontos };
    const ordem = ids.length <= LIMITE_EXATO ? exata(res, ids, pontos) : aproximada(res, ids, pontos);
    return { ordem, contradicoes: contradicoes(res, ordem), vitorias: pontos };
  };

  // o que vem do armazenamento: só chaves bem formadas (ids por ordem alfabética) e vencedores que existem no par
  const normalizar = (raw) => {
    const r = { v: VERSAO, res: {} };
    if (!raw || typeof raw !== "object" || raw.v !== VERSAO || !raw.res || typeof raw.res !== "object") return r;
    for (const k of Object.keys(raw.res)) {
      const m = /^(tt\d+)\|(tt\d+)$/.exec(k);
      const w = raw.res[k];
      if (!m || m[1] >= m[2] || (w !== m[1] && w !== m[2] && w !== "=")) continue;
      r.res[k] = w;
    }
    return r;
  };

  return { chave, pares, ordemDosPares, registar, remover, juntar, pendentes, progresso, vitorias, ordenar, normalizar };
})();

if (typeof module !== "undefined") module.exports = TierDuelos;
