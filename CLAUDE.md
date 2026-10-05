# Filmes na TV por rating IMDb

Projeto pessoal pequeno: recolher a programação de canais de filmes/séries portugueses, identificar os filmes, obter o rating IMDb de cada um e mostrar uma lista ordenada por rating.

Motivação: a NOS TV só deixa ver o que passou nos últimos 7 dias através do guia autenticado, sem URL por dia, o que torna o scraping impraticável. Em alternativa usa-se o site público tudonumclick.com.

## Objetivo real

O que interessa é saber **que bons filmes estão disponíveis para gravar**. Na NOS TV só se consegue ver o que passou nos últimos 7 dias (incluindo o próprio dia), por isso a página deve responder a duas perguntas:

1. **Para gravar já**: filmes que passaram nos últimos 7 dias (incluindo hoje), ordenados por rating IMDb, com canal, dia/hora e quanto tempo falta até deixarem de estar disponíveis.
2. **A vir**: filmes dos próximos dias (cerca de 5 a 6, o que o site mostra), ordenados por rating, para saber que vem aí algo bom.

O histórico completo desde o primeiro dia **não** é um objetivo. Mas, como o site só mostra cerca de 1 dia para trás, a secção "para gravar" só se constrói se o script correr **todos os dias**: um filme que passou há 4 dias só é conhecido porque foi recolhido na altura. Basta guardar uma janela móvel de cerca de 8 dias e podar o resto. Na primeira semana depois de ativar o agendamento, a secção "para gravar" vai estar incompleta.

Limitação a ter presente: a página mostra o que passou na grelha, não o que está confirmado como disponível no catch-up da NOS (direitos, canais sem gravação, etc.). Não verificado.

## Decisões tomadas

- Repositório no GitHub, **público** (o GitHub Pages gratuito exige repo público; confirmado pelo utilizador, que aceita que a página fique acessível a quem tiver o link).
- GitHub Actions com execução **diária** (cron) mais disparo manual. Semanal não serve: deixaria buracos, porque o site só mostra poucos dias.
- Resultado final: página no **GitHub Pages** (`filmes.html`), aberta no telemóvel através de um marcador.
- `TMDB_API_KEY` guardada como *secret* do repositório, nunca no código.
- Persistência entre execuções (o Actions começa sempre do zero): guardar no repo só `airings` e `matches` (pequenos, com poda de programas com mais de ~8 dias). O dataset de ratings do IMDb não se guarda; volta a ser descarregado em cada execução (~8 MB comprimidos).
- Por testar: se o tudonumclick.com aceita pedidos vindos dos servidores do GitHub.

## Estado atual

**Feito**
- Script único `filmes_tv.py`; credenciais lidas de `.env` local (gitignored; ver `.env.example`).
- Lista de 16 canais com slugs do tudonumclick.com, todos confirmados pelo utilizador (ver tabela abaixo).
- Pipeline completo no código: scraping -> SQLite -> TMDB -> dataset IMDb -> `filmes.html`.

**Validado em 2026-10-05 (execução local):** scraping dos 16 canais (~2300 programas, 3 a 10 de outubro, 0 avisos de "0 programas"), parser com testes (`python -m unittest discover -s tests`), datas ("Hoje" do site = data local, confirmado com a página "No AR"). robots.txt só proíbe `/ajax/` e `/cgi-bin/`.
**Matching TMDB (2026-10-05, 725 títulos):** 582 com correspondência, 143 sem. A 1.ª versão (só duração) dava 624 mas com erros graves (ex.: "Inferno" -> *Insidious Inferno*, "Bird" -> *Lady Bird*); a regra atual troca cobertura por precisão. O topo da lista foi revisto à mão e está correto. Ambiguidades por remakes com o mesmo título (Annie, Shaft, Passageiros) dependem só da duração e podem falhar. Os `(VP)` e a versão original aparecem como entradas separadas. Filmes de TV/Natal com título local ficam sem correspondência.
**Também validado:** download do dataset IMDb (1,7 M ratings em ~5 s) e geração do `filmes.html`.
**Por validar:** acesso a partir dos servidores do GitHub e execução de ponta a ponta com `python filmes_tv.py`.

Achados do HTML real: cada programa é um `div.channel_data` com a hora em `<b>HH:MM às HH:MM</b>` e o título em `<b class="ml10 dib">`; a página de cada dia **abre com o programa da noite anterior que atravessa a meia-noite** (o parser data-o no dia anterior). O NOS Studios tem emissões sobrepostas no próprio site (15 sobreposições). Alguns títulos trazem o ano, ex. "Pinóquio (2019)", e séries ("T12 - Ep. 3") passam o filtro de duração.

**Termos do site** (`/termos-e-condicoes/`, 2020): a secção "Cópia de conteúdos" proíbe reproduzir/distribuir a informação sem autorização. Uso pessoal a baixo ritmo parece compatível, mas publicar a grelha no GitHub Pages / `airings` num repo público é uma zona cinzenta; decisão pendente.

## Como funciona

1. **Scraping** (`discover_slugs`, `scrape_channel`, `parse_programs`): para cada canal pede `/programacao-tv/<slug>/` e depois cada dia listado na navegação da página (`/<slug>/<dia>/`). O parser não usa seletores CSS: lê o texto da página e procura linhas `HH:MM às HH:MM` seguidas do título. Guarda em `airings(channel, start, end, title)` com `INSERT OR IGNORE`, por isso correr várias vezes acumula histórico.
2. **Filtro de filmes**: considera filme qualquer programa com duração >= `MIN_MINUTES` (75). É uma heurística; não há categoria no site.
3. **Matching TMDB** (`match_title`, `choose`): pesquisa `/search/movie` em `pt-PT` (com `year` se o título trouxer "(2019)"; `(VP)` e `´` são normalizados; episódios "T12 - Ep. 3" são ignorados). Só vê detalhes de resultados cujo título (pt-PT ou original) seja parecido (`similarity` >= 0.85, ignorando acentos/maiúsculas; o prefixo antes de " - " ou ": " vale um pouco menos). Duração do slot vs. filme com tolerância assimétrica (slot pode ser até 60 min mais longo por publicidade, ou 25 mais curto); desempata por semelhança e depois por duração. Recurso: sem título parecido, aceita o 1.º resultado se tiver >= 1500 votos e duração a ±15 min (ex.: "Duna" vs "Dune: Parte Um"). Os falhanços ficam em `matches` com `imdb_id` NULL.
4. **Ratings**: descarrega `title.ratings.tsv.gz` de datasets.imdbws.com (refresca se tiver mais de 7 dias) para a tabela `ratings`; o join é local.
5. **Relatório** (`collect_films`, `report`): gera `filmes.html` com um filme por `imdb_id` (junta `(VP)` e variantes de maiúsculas) e três secções, todas ordenadas por rating (sem rating no fim): "A dar agora" (só se houver), "Para gravar" (emissões já terminadas nos últimos 7 dias, com "até <data> (faltam X)", a vermelho se faltar menos de 1 dia; prazo = início + 7 dias, **suposição não verificada** sobre como a NOS conta) e "A vir" (início no futuro). Um filme pode estar em "Para gravar" e "A vir", cada um só com as suas emissões. Termina com "Sem correspondência".

## Ficheiros

- `filmes_tv.py`: todo o código.
- `filmes.db`: SQLite (tabelas `airings`, `matches`, `ratings`). Gerado.
- `title.ratings.tsv.gz`: cache do dataset IMDb. Gerado.
- `filmes.html`: resultado. Gerado.

Os três ficheiros gerados não devem ir para o git.

## Executar

```
pip install requests beautifulsoup4
export TMDB_API_KEY=...     # chave v3 gratuita do themoviedb.org; nunca escrever no código
python filmes_tv.py
```

## Canais (todos confirmados pelo utilizador)

| Canal | Slug |
|---|---|
| Hollywood | hollywood |
| AXN | axn |
| AXN Movies | axn-black |
| AXN White | axn-white |
| STAR Channel | fox |
| STAR Life | fox-life |
| STAR Movies | fox-movies |
| STAR Crime | fox-crime |
| STAR Comedy | fox-comedy |
| SyFy | syfy |
| AMC | amc |
| NOS Studios | nos-studios |
| TVCine Top | tvc1 |
| TVCine Edition | tvc2 |
| TVCine Emotion | tvc3 |
| TVCine Action | tvc4 |

O Cinemundo foi retirado de propósito. Não voltar a acrescentar.

## O que se sabe do site (observado numa só página)

- URLs: `/programacao-tv/<slug>/` (hoje) e `/programacao-tv/<slug>/<dia>/` com `<dia>` em nomes de dias da semana sem acento (`segunda`, `terca`, ...) ou `ontem`. A navegação segue a ordem Hoje, Amanhã, dias seguintes, Ontem.
- Janela disponível: cerca de 1 dia para trás e 5 a 6 para a frente. Não chega aos 7+7 dias pedidos; o histórico só se constrói correndo o script regularmente.
- Cada programa tem hora de início/fim, título em português e sinopse curta. Não tem ano, título original, género nem categoria.
- A duração do slot é muito próxima da duração real do filme nos exemplos vistos (ex.: 150 min para Harry Potter e a Pedra Filosofal), mas pode ser diferente em canais com publicidade. Por confirmar.

## Riscos conhecidos / a verificar

- **Parser**: se a hora e o "às" estiverem em elementos separados, a regex linha a linha falha. O script avisa com "0 programas lidos" por canal. Ajustar `parse_programs` com base no HTML real.
- **Datas**: os offsets dos dias usam `date.today()` local. Na página lida, "Amanhã" apontava para domingo quando a data real já era domingo, o que sugere que o conteúdo lido estava em cache ou desfasado. Confirmar que "Hoje" no site coincide com a data local.
- **Matching**: títulos portugueses com grafias estranhas (ex.: "D´Artacão E Os Três Moscãoteiros") ou muito curtos ("Cantar!") podem falhar ou apanhar o filme errado. Os falhanços nunca são repetidos (ficam em `matches` com NULL).
- **Séries longas** podem passar o filtro de duração mas não vão ter correspondência em `/search/movie`; ficam na lista de "sem correspondência".
- **Termos de uso**: não foram verificados os termos nem o `robots.txt` do tudonumclick.com. Verificar antes de automatizar. Manter o ritmo baixo (`REQUEST_DELAY` = 1 s; cerca de 100 pedidos por execução).

## Por fazer

1. Correr o script, ver os avisos por canal e corrigir `parse_programs` conforme o HTML real.
2. Guardar 1 ou 2 páginas reais como fixtures e escrever testes simples para o parser.
3. Confirmar o ponto das datas ("Hoje" do site vs. data local).
4. Verificar `robots.txt` e termos do site.
5. Avaliar a qualidade do matching numa amostra real; ajustar a tolerância de duração e normalizar títulos (acentos/apóstrofos estranhos, sufixos como "- O Filme") se necessário.
6. Permitir repetir os falhanços de matching ao fim de algum tempo (hoje ficam para sempre como NULL).
7. ~~Dividir o relatório em duas secções~~ — feito (ver "Relatório" acima).
8. ~~Podar `airings` com mais de ~8 dias~~ — feito (`prune`, `KEEP_DAYS` = 8, chamada em `main()` depois do scraping; os `matches` não são podados).
9. Criar o repositório no GitHub, o workflow (cron diário + `workflow_dispatch`), o passo que guarda `airings`/`matches` entre execuções e o deploy para o GitHub Pages.
10. Avisar na página quando a janela de 7 dias ainda estiver incompleta (primeira semana).
11. Opcional: filtro de votos mínimos (para evitar notas altas com poucos votos), filtros por canal/rating na página.

## Convenções

- Python 3, dependências apenas `requests` e `beautifulsoup4`.
- Nunca colocar chaves no código; usar variáveis de ambiente.
- Não aumentar a frequência de pedidos ao tudonumclick.com sem motivo.
- Código e comentários em português, como já está.
- Ao descrever resultados ou limitações, preferir linguagem calibrada ("parece", "não verificado") a afirmações definitivas quando não foi testado.
