# Tierlist pessoal de filmes: desenho

Data: 2026-10-13

## Objetivo

Permitir ordenar numa tierlist, segundo o gosto do utilizador, os filmes que já viu. Os tiers são personalizáveis. Adicionam-se e removem-se filmes e movem-se com drag and drop (rato e toque). Vive como uma vista nova dentro de `filmes.html`.

## Decisões (confirmadas pelo utilizador)

| Tema | Decisão |
|---|---|
| Origem dos filmes | Os marcados como vistos (sugestões) **e** pesquisa ao vivo no TMDB |
| Chave TMDB | O utilizador cola-a no browser (uma vez por dispositivo); fica em `localStorage`, nunca no repo |
| Localização | Vista dentro da mesma página, alternada na barra fixa ("Na TV" / "Tierlist") |
| Persistência | `localStorage` + exportar/importar JSON |
| Tiers | Renomear, cor, reordenar, adicionar e remover. Por omissão: S, A, B, C, D |
| Ordem | Livre, por arrasto dentro do tier (esquerda = melhor). Área "por classificar" para os vistos sem tier |
| Visto | Adicionar à tierlist marca como visto. Remover (✕) tira só da tierlist |
| Toque | O arrasto com o dedo tem de funcionar |
| Biblioteca de arrasto | SortableJS (MIT, ~45 KB) embutido no HTML, sem CDN |

## Dados

Chave `filmes-tv:tierlist` no `localStorage`:

```
{v:1,
 tiers:[{id, nome, cor}],                 // a ordem do array é a ordem das linhas
 itens:{<imdb_id>:{tier, pos}},           // tier = null → por classificar
 filmes:{<imdb_id>:{titulo, ano, poster}} // metadados, para filmes que já não estão na página
}
```

O ID do IMDb vem do TMDB (`external_ids`) e coincide com o das marcas `vistos` (`filmes-tv:marcas`). Os metadados ficam guardados porque um filme pesquisado, ou que já saiu da grelha, não está no HTML.

## Interface

**Barra fixa.** Comutador "Na TV" / "Tierlist". Na vista Tierlist escondem-se os atalhos de secção, a pesquisa da grelha e os botões de visto e de guardados. A vista não se guarda entre visitas. `?v=tierlist` abre diretamente nela.

**Vista Tierlist** (de cima para baixo):
1. **Linhas de tiers:** etiqueta colorida à esquerda com o nome; à direita os posters em fila, que quebra para a linha seguinte. Cada poster tem um ✕ pequeno. Sem poster, retângulo vazio com o título.
2. **Editar tiers:** botão que ativa o modo de edição. Cada etiqueta permite renomear, escolher a cor (paleta fixa de cerca de 8 cores, sem vermelho nem ouro, reservados a "gravar" e ao rating), apagar e arrastar a linha. Botão "+ tier" no fim. Apagar um tier com filmes devolve-os a "por classificar".
3. **Pesquisa para adicionar:** campo que consulta o TMDB (poster, título, ano). Tocar num resultado põe o filme em "por classificar" e marca-o como visto. A primeira pesquisa pede a chave TMDB, com link para a obter.
4. **Por classificar:** área por baixo, com os vistos sem tier e os recém-adicionados. Aceita também filmes largados de volta (desclassificar sem remover).
5. **Exportar / Importar:** o primeiro descarrega um JSON; o segundo escolhe um ficheiro e pede confirmação, porque substitui a tierlist atual.

**Remover (✕):** devolve o filme a "por classificar". Como adicionar marca como visto, a forma de o tirar de vez é desmarcar o visto. Um "apagar de vez" explícito fica fora de âmbito, a menos que o utilizador o peça.

**Estilo:** conceito OSD já existente (fundo azul, texto branco); as cores de tier só nas etiquetas.

## Implementação

- SortableJS embutido pelo `report` em `filmes_tv.py`, como `estilo.css` e `pagina.js`. A página continua num só ficheiro.
- Listas ligadas (tiers + por classificar) para mover entre elas; lista própria para reordenar as linhas de tiers; press longo no toque para não colidir com o scroll.
- A lógica de estado (normalizar, mover, remover, apagar tier, reordenar tiers, importar, validar JSON) fica em funções puras separadas da DOM, para ser testável.
- O servidor só gera o esqueleto da vista (escondido até o JS a mostrar).

## Erros e casos limite

- Sem chave TMDB ou chave inválida (401): a pesquisa mostra o campo para colar a chave; uma chave recusada é apagada e pedida de novo.
- Sem rede ou limite do TMDB: mensagem curta nos resultados; o resto da tierlist funciona porque é local.
- `localStorage` bloqueado: a tierlist vale só enquanto a página está aberta, com aviso; exportar continua disponível.
- Importar JSON inválido ou de versão desconhecida: recusa com mensagem e não toca nos dados atuais.
- Duplicados: um filme só aparece uma vez (chave = ID do IMDb); pesquisar um que já lá está mostra "já na tierlist".
- Sincronização entre separadores: evento `storage`, como as marcas.
- Filme sem ID do IMDb no TMDB: aparece nos resultados mas não pode ser adicionado.

## Testes

- Testes unitários da lógica de estado (extraída para um módulo JS pequeno, exercido no Chromium) e do que for gerado em Python.
- `tools/verificar_tierlist.py`: Chromium headless com oráculo em Python, como os outros. Cobre criar e apagar tiers, mover filmes por arrasto (rato e toque simulado), remover, persistência após recarregar, exportar e importar, `localStorage` bloqueado e a pesquisa TMDB com resposta simulada (sem rede nem chave reais).
- `tools/capturar.py` ganha `--vista tierlist`.
- Por validar: o toque num telemóvel real.

## Fora de âmbito

Partilhar como imagem, várias tierlists, sincronização automática entre dispositivos, anular, notas por filme, ordenar por rating dentro do tier, "apagar de vez" explícito.

## Ficheiros afetados

`pagina.js`, `estilo.css`, `filmes_tv.py`, `tools/`, `tests/`, `CLAUDE.md`.
