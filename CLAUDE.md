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
- Persistência entre execuções (decidido: no repo): `data/airings.csv` e `data/matches.csv` (ordenados, gerados por `export_state`, lidos por `import_state`); o Actions faz commit deles. O dataset de ratings do IMDb não se guarda; volta a ser descarregado em cada execução (~8 MB comprimidos). Decisão A sobre os termos do site: repo e página públicos com a grelha, assumido pelo utilizador.
- Cron diário configurado para as 05:17 UTC (06:17 Lisboa no verão). **Na prática a execução agendada corre por volta das 12:00 de Lisboa** (o GitHub atrasa-a); o utilizador aceitou isto e dispara o workflow à mão de manhã quando quer a página fresca, antes dessa hora. Não é um problema a resolver. Definido em `.github/workflows/atualizar.yml`. Se nenhum canal for lido, o script falha de propósito em vez de publicar dados antigos. Página: https://filipeoliveira05.github.io/films-tv/

## Estado atual

**Feito**
- Script único `filmes_tv.py`; credenciais lidas de `.env` local (gitignored; ver `.env.example`).
- Lista de 16 canais com slugs do tudonumclick.com, todos confirmados pelo utilizador (ver tabela abaixo).
- Pipeline completo no código: scraping -> SQLite -> TMDB -> dataset IMDb -> `filmes.html`.

**Validado em 2026-10-05 (execução local):** scraping dos 16 canais (~2300 programas, 3 a 10 de outubro, 0 avisos de "0 programas"), parser com testes (`python -m unittest discover -s tests`), datas ("Hoje" do site = data local, confirmado com a página "No AR"). robots.txt só proíbe `/ajax/` e `/cgi-bin/`.
**Matching TMDB (2026-10-05, 725 títulos):** 582 com correspondência, 143 sem. A 1.ª versão (só duração) dava 624 mas com erros graves (ex.: "Inferno" -> *Insidious Inferno*, "Bird" -> *Lady Bird*); a regra atual troca cobertura por precisão. O topo da lista foi revisto à mão e está correto. Ambiguidades por remakes com o mesmo título (Annie, Shaft, Passageiros) dependem só da duração e podem falhar. Os `(VP)` e a versão original aparecem como entradas separadas. Filmes de TV/Natal com título local ficam sem correspondência.
**Também validado:** download do dataset IMDb (1,7 M ratings em ~5 s) e geração do `filmes.html`.
**Validado no GitHub (2026-10-05, execução manual):** os servidores do GitHub conseguem ler o tudonumclick.com (16 canais, mesmos totais que localmente), testes e deploy para o Pages passaram, a página está online. **Cron e bot (verificado em 2026-10-12 com `gh run list`):** o cron (`schedule`) corre todos os dias e o bot faz commit de `data/`, mas o GitHub atrasa-o muito: as execuções agendadas começam por volta das 11:30 UTC e não às 05:00 (o utilizador tem disparado o workflow à mão de manhã). Uma falhou (11/10): *timeout* de ligação na primeira chamada ao site (`discover_slugs`), sem retentativa; corrigido com `RETRY_WAITS` em `get()` e recurso a `KNOWN_SLUGS`. **Primeira execução completa com poster, elenco e marcas (2026-10-13, disparo manual):** passou; 90 filmes novos identificados e 0 por preencher em poster e elenco (os novos trazem ambos do matching); o bot fez commit. Por validar: o aspeto/toque no telemóvel.

Achados do HTML real: cada programa é um `div.channel_data` com a hora em `<b>HH:MM às HH:MM</b>` e o título em `<b class="ml10 dib">`; a página de cada dia **abre com o programa da noite anterior que atravessa a meia-noite** (o parser data-o no dia anterior). O NOS Studios tem emissões sobrepostas no próprio site (15 sobreposições). Alguns títulos trazem o ano, ex. "Pinóquio (2019)", e séries ("T12 - Ep. 3") passam o filtro de duração.

**Termos do site** (`/termos-e-condicoes/`, 2020): a secção "Cópia de conteúdos" proíbe reproduzir/distribuir a informação sem autorização. Uso pessoal a baixo ritmo parece compatível, mas publicar a grelha no GitHub Pages / `airings` num repo público é uma zona cinzenta. Decisão do utilizador (2026-10-05): seguir com repo e página públicos (opção A), assumindo esse risco.

## GitHub Actions (`.github/workflows/atualizar.yml`)

- **Gatilhos:** `schedule` (cron `17 5 * * *`, UTC), `workflow_dispatch` (com opção "só página") e `push` em `main` só se mudar `estilo.css`, `pagina.js`, `filmes_tv.py`, `tierlist.js`, `tierlist_estado.js`, `vendor/Sortable.min.js` ou o próprio workflow. Os pushes do bot (só `data/`) e os de documentação não o disparam.
- **Modo completo** (cron e disparo manual): corre os testes, `python filmes_tv.py` (scraping, matching, posters, elenco, ratings, página), faz commit de `data/` com `git pull --rebase` antes do push (aguenta pushes teus a meio) e publica no Pages. Se nenhum canal for lido, falha de propósito e não publica.
- **Modo "só página"** (push, ou disparo manual com a opção): `python filmes_tv.py --relatorio` cria a base de dados do zero, importa `data/*.csv`, descarrega os ratings e gera a página. **Sem pedidos ao tudonumclick.com nem ao TMDB**, não precisa da chave e não faz commit. O `checkout` usa a ponta do ramo, para apanhar os dados mais recentes do bot.
- `concurrency: filmes` (uma execução de cada vez). `data/atualizado.txt` é reescrito em cada execução completa, por isso o bot faz commit todos os dias.
- **O cron agendado corre por volta das 12:00 de Lisboa**, não à hora configurada: o GitHub atrasa as execuções agendadas (aceite pelo utilizador, que dispara à mão de manhã com `gh workflow run atualizar.yml` ou pelo separador Actions). Já falhou uma vez por timeout do site (11/10), entretanto tratado com retentativas.
- Versões das actions: `checkout@v4`, `setup-python@v5`, `upload-pages-artifact@v3`, `deploy-pages@v4`. O GitHub avisa que `checkout` e `setup-python` correm em Node 20 (descontinuado); rever.

## Design da página

Conceito: o menu no ecrã (OSD) de um gravador: fundo azul de "sem sinal", texto branco, ponto vermelho de REC, verde de PLAY. Cada cor tem um só significado (vermelho = gravar/urgente, verde = a dar agora, ouro = rating >= 8). Tipo: Archivo variável (Google Fonts, eixo de largura: condensado nos títulos, expandido nos ratings). Elemento central: a "fita", barra por emissão que mostra a fração da janela de 7 dias que ainda resta (vermelha se faltar menos de 1 dia). Funciona sem JavaScript (o script só acrescenta o recálculo ao longo do dia, a pesquisa e as marcas). Pensado primeiro para telemóvel; "Sem correspondência" vem recolhida. Para ver alterações, gerar a página e fotografá-la com o Chromium headless do Playwright (`~/.cache/ms-playwright`).

**Página viva:** o HTML é gerado em cada execução completa do workflow (em princípio uma por dia), mas `pagina.js` (embutido) recalcula no browser, ao abrir e de minuto a minuto, em que secção está cada emissão ("A dar agora", "Para gravar", "A vir"), os "faltam/em", a fita, o estado urgente e as contagens, a partir de `data-start`/`data-end` (segundos UTC; `epoch()` converte a hora de Lisboa). Sem JavaScript a página continua certa à hora da geração. Para testar outra hora: `?t=<milissegundos>` no endereço. Verificado a comparar o JS com o gerador Python (oráculo) em 7 horas simuladas. O aviso de histórico incompleto é estático (da geração). A hora "Atualizado" é a da **última recolha de dados** (`data/atualizado.txt`), e não a da geração da página.

## Pesquisa

Campo "Pesquisar filme, ator" na segunda linha da barra fixa (só aparece com JavaScript). Filtra no sítio, nas três secções, com as contagens (atalhos e títulos) a refletir o resultado; "A dar agora" esconde-se se ficar vazia. "Sem correspondência" também se filtra e abre-se sozinha se tiver resultados (fecha ao limpar). Um filme casa se **o título** (em português ou original) tem todas as palavras escritas, sem acentos nem maiúsculas, **ou** se **um mesmo ator** do elenco tem todas elas (por pessoa, para \"tom hanks\" não apanhar Tom Cruise + Colin Hanks). Cada filme mostra sempre \"Com A, B, C\" (os 3 primeiros do elenco); ao pesquisar um ator, os nomes que casaram ficam a negrito e sublinhados e, se estiverem depois do 3.º, juntam-se à linha (no máximo 3 extras). Esc ou ✕ limpa; `?q=texto` no endereço abre já com uma pesquisa.

Como está feito: `search_key()` (Python) normaliza o texto e `film_item` põe-no em `data-search` (também nos `<li>` de "Sem correspondência"); `pagina.js` normaliza o que se escreve da mesma forma e filtra dentro do `render()` (por isso convive com o recálculo de minuto a minuto). O elenco completo (decisão do utilizador, contra a recomendação de top 10) está em `matches.elenco` (`Nome|Nome|...` em ordem de crédito; `-` = o TMDB não tem), vem do TMDB no matching (`append_to_response=credits`, sem pedido extra) ou de `fill_elenco` (`/find` + `/movie/<id>/credits`, 2 pedidos por filme) para os já identificados, e vai para a página em `data-cast` (nomes originais, escapados; o `pagina.js` normaliza-os uma vez ao carregar). Custo medido numa amostra de 25 filmes: mediana de 45 nomes (3 a 85), ~650 bytes por filme. **A pesquisa por canal** é diferente: é um filtro por **emissão** (mostrar só as emissões desse canal), não por filme, e precisa do seu próprio desenho. Fora de âmbito por agora: realce do texto, pesquisa aproximada, ordenação por relevância.

Verificação: `tools/verificar_pesquisa.py` (oráculo em Python que calcula, a partir do `data-search` e do `data-cast`, o que cada pesquisa deve devolver, comparado com o DOM do Chromium headless via `?q=`, mais o caminho de escrever no campo e de limpar). `content-visibility: auto` nas linhas baixou a reconstrução da lista inteira (mais de mil filmes) de ~400 ms para ~70 ms em desktop; em telemóvel real não medido.

## Marcas: visto e guardado

Cada filme tem dois botões na coluna do rating: **olho** (já vi) e **marcador** (guardar para gravar). As marcas são **por filme** (ID do IMDb), por isso valem em todas as secções onde o filme aparece, e guardam-se **só neste browser** (`localStorage`, chave `filmes-tv:marcas`, `{v:1, guardados, vistos, ocultarVistos}`): telemóvel e computador não partilham, e limpar os dados do browser apaga-as. Sem armazenamento (modo privado) valem só enquanto a página está aberta. Há sincronização entre separadores abertos (evento `storage`). O `localStorage` é partilhado por tudo o que viva em `filipeoliveira05.github.io`, por isso a chave tem prefixo (`filmes-tv:`).
- **Visto:** a linha fica a ~55% de opacidade e o poster a preto e branco; os botões ficam nítidos. O filme continua na lista.
- **Guardados:** botão com marcador e contagem ao lado do campo de pesquisa. Premido, a página mostra só os guardados, nas mesmas três secções (com prazo e fita) e combinável com a pesquisa; "Sem correspondência" esconde-se (não tem ID, não se pode guardar). A contagem e o filtro só consideram filmes com alguma emissão na página; se houver guardados sem emissão, aparece a nota "N guardados já não estão disponíveis (reaparecem se voltarem a passar)". O modo não se guarda entre visitas.
- **Ocultar vistos:** botão com olho riscado e a contagem de vistos. Esconde os vistos das listas; **a preferência guarda-se**. Marcar como visto com isto ligado faz o filme desaparecer logo (não há anular; desliga o filtro para o ver).
- Os dois botões de filtro estão na linha do campo de pesquisa (e não nos atalhos, que com 4 itens deixavam de caber em 390 px).
- Não implementado: exportar/importar, sincronizar entre dispositivos, anular, marcar vários de uma vez.

O servidor só gera os botões (escondidos até o JS os mostrar); o resto está no `pagina.js` dentro do `render()`. O HTML cru cresce ~0,6 MB (botões repetidos) mas comprimido fica igual.

## Tierlist

Vista "Tierlist" na mesma página: o comutador "Na TV" / "Tierlist" fica na barra fixa (só aparece com JavaScript); `?v=tierlist` abre já nela. O utilizador ordena por arrasto os filmes que já viu em tiers personalizáveis (por omissão 10, 9, 8, 7, 6, numa rampa de lima a roxo; quem já tem uma tierlist guardada mantém os seus tiers). Desenho em `docs/superpowers/specs/2026-10-13-tierlist-design.md`, plano em `docs/superpowers/plans/2026-10-13-tierlist.md`.

- **Dados:** `localStorage`, chave `filmes-tv:tierlist`, `{v:1, tiers:[{id,nome,cor}], itens:{<imdb_id>:{tier,pos}}, filmes:{<imdb_id>:{titulo,ano,poster}}}`. Só neste browser (como as marcas): limpar os dados do browser apaga-a; a única cópia de segurança são os botões **Exportar** / **Importar** (JSON; importar pede confirmação, substitui a tierlist e marca os filmes importados como vistos). Os metadados ficam guardados para um filme continuar a aparecer depois de sair da grelha.
- **Regras:** "por classificar" = filmes explícitos sem tier + vistos que a grelha conhece e nunca foram postos num tier (um visto sem metadados, que já saiu da grelha, não aparece). Adicionar um filme à tierlist marca-o como visto. O ✕ de um cartão só aparece com o rato por cima (ou foco do teclado) e, no telemóvel, depois de tocar no cartão (classe `.tl-sel`, só visual; tocar noutro sítio esconde-o); devolve o filme a "por classificar" (não o apaga; para o tirar de vez, desmarcar o visto). Apagar um tier devolve os filmes a "por classificar". Tiers: renomear (máx. 24 caracteres), cor (8 da paleta, sem vermelho nem ouro), adicionar, apagar, reordenar (modo "Editar tiers").
- **Pesquisa de filmes para adicionar:** ao vivo no TMDB (`/search/movie` em pt-PT e `/movie/<id>/external_ids` para obter o ID do IMDb). A chave v3 é **colada pelo utilizador no browser** e guarda-se em `filmes-tv:tmdb-chave` (uma vez por dispositivo): nunca no código nem no repo. Chave recusada (401) é apagada e pedida de novo; sem rede, mensagem; filme sem ID do IMDb não se adiciona.
- **Arrasto:** SortableJS 1.15.6 (MIT) copiado para `vendor/Sortable.min.js` e embutido no HTML (sem CDN). `forceFallback` (eventos de ponteiro, igual para rato e dedo) com press longo (220 ms) no toque, para não colidir com o scroll.
- **Código:** `tierlist_estado.js` (estado puro, sem DOM; testado com `node --test` em `tests/js/` através de `tests/test_tierlist_js.py`, que se salta se não houver `node`), `tierlist.js` (vista), ponte `window.FilmesTV` em `pagina.js` (vistos, `marcarVisto`, `aoMudarMarcas`, `metaFilme`). O servidor (`views_html`, `tierlist_html` em `filmes_tv.py`) só gera o esqueleto; `window.FilmesTV.tierlist` é também o gancho das verificações.
- **Verificação:** `tools/verificar_tierlist.py` (Chromium headless, página real; inclui arrasto com eventos de ponteiro sintéticos, edição de tiers, pesquisa TMDB com `fetch` simulado, exportar/importar, `localStorage` bloqueado; demora ~2 minutos) e `tools/capturar.py --vista tierlist --tierlist-demo [--editar]`.
- **Toque:** `tools/verificar_toque.py` (+ `tools/_toque.mjs`, só `node` 22 e o Chromium do Playwright, sem dependências) faz gestos de toque **reais** por CDP num ecrã de telemóvel emulado: press longo e arrastar mudam o filme de tier sem rolar a página, e deslizar na vertical sobre um cartão rola-a. Passa, mas é emulação em Chromium de secretária, não um telemóvel. No telemóvel real (13/10) o arrasto falhava e o press longo num poster abria o menu do Chrome ("abrir imagem noutro separador"), que cancela o toque; causa provável: a `<img>` recebia o press. Correção: `pointer-events: none` nas imagens dos cartões e `contextmenu` evitado sobre os cartões (S14 em `verificar_tierlist.py`). **Confirmado pelo utilizador num telemóvel real (13/10): o arrasto com o dedo funciona.** Se voltar a falhar noutro aparelho, as hipóteses seguintes são `supportPointer: false` no Sortable (caminho de eventos de toque, que bloqueia o scroll depois do press longo) e `touch-action: none`; plano B: um "Mover para…" em cada cartão.
- **Não verificado:** o arrasto com o rato só se simula com eventos de ponteiro, e a reordenação das linhas de tiers por arrasto só se verificou pelo gancho (`soltarTier`); o aspeto no telemóvel foi visto pelo utilizador, sem queixas além do arrasto (já corrigido). A reordenação das linhas de tiers por arrasto só se verificou pelo gancho (`soltarTier`), não com o rato.
- **Duelos:** botão "Duelos" na barra da tierlist; abre um ecrã por cima onde se escolhe um tier e se duelam **todos os pares** dos filmes dele (ordem aleatória, sem o mesmo filme em duelos seguidos, lado aleatório; "Empate / não sei" vale meio ponto; "Desfazer"). No fim mostra a **ordem sugerida**, que é a que **contradiz menos duelos** (um duelo é contradito se o vencedor ficou abaixo do perdedor): exata até 18 filmes (programação dinâmica sobre subconjuntos, ~85 ms com 18) e aproximada acima disso; o desempate usa as vitórias. Havendo ciclos aparece o aviso com as contradições e "Rever conflitos (N)" repete só esses duelos. "Aplicar ordem" só muda as **posições dentro do tier** (`ordenarTier` em `tierlist_estado.js`): não mexe em tiers, nomes, cores nem em que tier está cada filme. Os resultados guardam-se à parte, em `filmes-tv:duelos` (`{v:1, res:{"ttA|ttB": id vencedor | "="}}`, por **par de filmes e não por tier**, por isso sobrevivem se um filme mudar de tier) e **vão no Exportar** (campo `duelos` do JSON, só se houver; `T.exportar` não os leva, é o `tierlist.js` que o acrescenta). **Importar** substitui a tierlist mas **junta** os duelos do ficheiro aos que já existem (no mesmo par vale o do ficheiro); um ficheiro antigo, sem o campo, não apaga duelos; duelos mal formados são ignorados (`DU.normalizar`). Limpar o browser apaga-os se não houver exportação. Código em `tierlist_duelos.js` (puro, `tests/js/tierlist_duelos.test.js`), vista em `tierlist.js`, cenários S15 a S19 em `verificar_tierlist.py`, capturas com `tools/capturar.py --tierlist-demo --duelos menu|duelo|ordem|conflito`.
- **Fora de âmbito:** partilhar como imagem, várias tierlists, sincronização automática entre dispositivos, anular, notas por filme, ordenar por rating dentro do tier, "apagar de vez" explícito.

## Verificação no browser (`tools/`)

Precisam do Chromium do Playwright (`~/.cache/ms-playwright`) e do `filmes.db` local; não fazem parte do `unittest`. Cada script compara o JS da página com um oráculo em Python e termina com código 1 se falhar: `tools/verificar_horas.py` (recálculo de secções, prazos e fitas em 7 horas simuladas), `tools/verificar_pesquisa.py` (título, ator, "Sem correspondência", escrever e limpar), `tools/verificar_marcas.py` (visto, guardar, filtros, persistência, nota, localStorage bloqueado, separadores). `tools/capturar.py` tira capturas da página (telemóvel por omissão; `--q`, `--css`, `--marcar`, `--vistos`, `--ocultar`, `--guardados-modo`). `tools/verificar_tierlist.py` (tierlist: ver a secção "Tierlist"). `tools/_nav.py` é a base comum (`correr` injeta um cenário na página e devolve o resultado). **Antes isto vivia no scratchpad e perdeu-se; manter aqui.**

## Posters

Cada filme mostra o poster à direita (no telemóvel as emissões ocupam a largura toda por baixo; em ecrã largo ficam ao lado). Vêm do TMDB: `matches.poster` guarda o `poster_path` (preenchido no matching, ou por `fill_posters` via `/find/<imdb_id>` para os já identificados) e a página liga diretamente a `image.tmdb.org/t/p/w185` (`loading=lazy`, sem guardar imagens no repo). `-` em `poster` = o TMDB não tem poster (não voltar a perguntar); sem poster aparece um retângulo vazio com a mesma proporção. Os termos do TMDB exigem atribuição também para imagens: rodapé com logótipo e texto. O push em modo "só página" mostra posters porque estão em `data/matches.csv`.

## Como funciona

1. **Scraping** (`discover_slugs`, `scrape_channel`, `parse_programs`): para cada canal pede `/programacao-tv/<slug>/` e depois cada dia listado na navegação da página (`/<slug>/<dia>/`). O parser não usa seletores CSS: lê o texto da página e procura linhas `HH:MM às HH:MM` seguidas do título. Guarda em `airings(channel, start, end, title)` com `INSERT OR IGNORE`, por isso correr várias vezes acumula histórico.
2. **Filtro de filmes**: considera filme qualquer programa com duração >= `MIN_MINUTES` (75). É uma heurística; não há categoria no site.
3. **Matching TMDB** (`match_title`, `choose`): pesquisa `/search/movie` em `pt-PT` (com `year` se o título trouxer "(2019)"; `(VP)` e `´` são normalizados; episódios "T12 - Ep. 3" são ignorados). Só vê detalhes de resultados cujo título (pt-PT ou original) seja parecido (`similarity` >= 0.85, ignorando acentos/maiúsculas; o prefixo antes de " - " ou ": " vale um pouco menos). Duração do slot vs. filme com tolerância assimétrica (slot pode ser até 60 min mais longo por publicidade, ou 25 mais curto); desempata por semelhança e depois por duração. Recurso: sem título parecido, aceita o 1.º resultado se tiver >= 1500 votos e duração a ±15 min (ex.: "Duna" vs "Dune: Parte Um"). Os falhanços ficam em `matches` com `imdb_id` NULL e são repetidos ao fim de `RETRY_DAYS` (30). Devolve também o `poster_path` e o elenco (`append_to_response=external_ids,credits`).
4. **Ratings**: descarrega `title.ratings.tsv.gz` de datasets.imdbws.com (refresca se tiver mais de 7 dias) para a tabela `ratings`; o join é local.
5. **Relatório** (`collect_films`, `report`): gera `filmes.html` com um filme por `imdb_id` (junta `(VP)` e variantes de maiúsculas) e três secções, todas ordenadas por rating (sem rating no fim): "A dar agora" (só se houver), "Para gravar" (emissões já terminadas nos últimos 7 dias, com "até <data> (faltam X)", a vermelho se faltar menos de 1 dia; prazo = início + 7 dias, **suposição não verificada** sobre como a NOS conta) e "A vir" (início no futuro). Um filme pode estar em "Para gravar" e "A vir", cada um só com as suas emissões. Termina com "Sem correspondência".

## Ficheiros

- `filmes_tv.py`: todo o código.
- `tmdb.svg`: logótipo oficial do TMDB (da página de atribuição deles), embutido no rodapé.
- `estilo.css` e `pagina.js`: o estilo e o script da página; são embutidos em `filmes.html` pelo `report` (a página continua num só ficheiro).
- `tierlist_estado.js`, `tierlist.js` e `vendor/Sortable.min.js` (com `vendor/Sortable.LICENSE`): a vista Tierlist (ver a secção "Tierlist"); também embutidos.
- `docs/superpowers/`: desenho e plano da tierlist.
- `tests/`: testes (`python -m unittest discover -s tests`).
- `dev.py`: servidor local com recarregamento automático, só para desenvolvimento.
- `tools/`: verificações no browser e captura de ecrã (ver "Verificação no browser").
- `data/`: `airings.csv`, `matches.csv` e `atualizado.txt` (hora da última recolha), o estado guardado no repo.
- `.github/workflows/atualizar.yml`: o workflow (ver "GitHub Actions"). `requirements.txt`: `requests` e `beautifulsoup4`. `.env.example`: modelo do `.env` local (com a `TMDB_API_KEY`; o `.env` está no `.gitignore`).
- `filmes.db`: SQLite (tabelas `airings`, `matches`, `ratings`). Gerado.
- `title.ratings.tsv.gz`: cache do dataset IMDb. Gerado.
- `filmes.html`: resultado. Gerado.

Os três ficheiros gerados não devem ir para o git.

## Executar

Atenção: `data/*.csv` é atualizado pelo bot do Actions todos os dias. Antes de correr o script localmente, faz `git pull`, e não faças commit dos CSV de uma execução local sem necessidade (podem colidir com os do bot).

```
pip install requests beautifulsoup4
export TMDB_API_KEY=...     # chave v3 gratuita do themoviedb.org; nunca escrever no código
python filmes_tv.py
```

### Mexer no visual sem fazer push

`python dev.py` abre um servidor em http://localhost:8000: regenera a página a cada pedido e recarrega o browser sozinho quando gravas `estilo.css`, `pagina.js` ou `filmes_tv.py` (o aviso de recarregar só existe nesse servidor; se o código tiver um erro, o erro aparece no browser). Usa o `filmes.db` local e junta `data/*.csv`, sem pedidos de rede. Alternativa manual: `python filmes_tv.py --relatorio` e abrir `filmes.html`. Vista de telemóvel: F12 e Ctrl+Shift+M. Outra hora: `?t=<milissegundos>`. Para ir para o site online basta fazer push: se mexeres em `estilo.css`, `pagina.js`, `filmes_tv.py` ou no workflow, o push dispara sozinho o workflow em modo "só página" (cerca de 1 minuto, sem pedidos ao site; ver "GitHub Actions").

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

- **Origem dos horários:** o parser depende da estrutura HTML do tudonumclick.com (um `div.channel_data` por programa). Se mudar, o script avisa com "0 programas lidos" por canal e, se nenhum canal for lido, falha de propósito. Termos do site: zona cinzenta assumida (opção A).
- **Cron do GitHub** falhado (o atraso habitual está aceite, ver "GitHub Actions"); a "Para gravar" só fica completa com execuções diárias (um dia falhado é recuperado pelo "ontem" do site, dois seguidos perdem um dia).
- **Matching:** remakes com o mesmo título dependem só da duração; filmes de TV/Natal com título local ficam sem correspondência; um match errado mostra também o poster e o elenco errados.
- **Dependências externas da página:** Google Fonts (sem rede cai para a fonte do sistema) e `image.tmdb.org` (posters); os termos do TMDB exigem a atribuição que está no rodapé.
- **Marcas só no browser:** limpar os dados do browser apaga-as; telemóvel e computador não partilham.
- **Tamanho:** o HTML tem ~2,5 MB crus e ~580 KB comprimidos; cresce com a janela de dados e o elenco. `data/matches.csv` nunca é podada (ver "Por fazer", ponto 12).
- **Prazo de "Para gravar"** (início + 7 dias): suposição não verificada sobre como a NOS conta.
- **Telemóvel real:** aspeto, tamanho dos toques (40 px) e desempenho nunca foram vistos num telemóvel; só em capturas do Chromium.

## Por fazer

1. ~~Correr o script e corrigir `parse_programs`~~ — feito (0 avisos nos 16 canais; só foi preciso tratar o programa que atravessa a meia-noite).
2. ~~Fixtures e testes do parser~~ — feito (`tests/`; fixtures são excertos reduzidos, por causa dos termos do site).
3. ~~Datas~~ — feito ("Hoje" do site = data local, confirmado com a página "No AR").
4. ~~robots.txt e termos~~ — feito (ver "Termos do site" acima; publicação pública assumida pelo utilizador).
5. ~~Matching~~ — avaliado e reescrito (ver "Matching TMDB" acima). Continuam por melhorar os sem correspondência (143 em 5/10, 235 em 13/10, a janela cresceu) e os remakes ambíguos.
6. ~~Repetir falhanços de matching~~ — feito (`RETRY_DAYS` = 30, coluna `matches.checked`).
7. ~~Dividir o relatório em duas secções~~ — feito (ver "Relatório" acima).
8. ~~Podar `airings` com mais de ~8 dias~~ — feito (`prune`, `KEEP_DAYS` = 8, chamada em `main()` depois do scraping; os `matches` não são podados).
9. ~~GitHub Actions + Pages~~ — feito e executado com sucesso à mão em 2026-10-05 (secret, Pages com Source = GitHub Actions e permissões de escrita já configurados). O cron e o commit de dados pelo bot funcionam (ver "Cron e bot"), mas com muito atraso.
10. ~~Avisar quando a janela de 7 dias está incompleta~~ — feito (`history_notice`).
11. ~~Pesquisa por nome e por ator~~ — feita (ver "Pesquisa"). Por fazer: pesquisa por canal.
12. Podar `matches` sem nenhuma emissão há muito tempo (proposta: 90 dias; se o filme voltar, volta a ser identificado). Adiada por decisão do utilizador. Agora pesa mais: o elenco acrescenta ~650 bytes por linha de `data/matches.csv`, que nunca é podada.
13. ~~Marcas de visto e guardado, filtro Guardados e Ocultar vistos~~ — feitas (ver "Marcas"). Por fazer, se fizer falta: exportar/importar as marcas (limpar o browser apaga-as), anular ao marcar visto com "ocultar" ligado.
14. ~~Tierlist pessoal~~ — feita (ver "Tierlist"). Por validar: arrasto com o dedo e aspeto num telemóvel real.
15. Opcional: filtro de votos mínimos (para evitar notas altas com poucos votos), filtros por canal/rating na página.

## Retomar numa sessão nova

Estado em 2026-10-13: tudo está commitado e enviado para o GitHub; a página online está atualizada. `python -m unittest discover -s tests` (147 testes, incluindo os de `node --test` da tierlist) passa. As verificações no browser estão em `tools/` (precisam do Chromium do Playwright e do `filmes.db`; se faltar, `python filmes_tv.py --relatorio`). **Coisas que nunca devem viver só no scratchpad ou na conversa:** scripts de verificação e decisões; tudo o que importa deve estar neste ficheiro ou no repo.

Forma de trabalhar combinada: antes de uma funcionalidade nova, perguntas **uma de cada vez** com opções e recomendação, depois um desenho curto e só se implementa com aprovação; testes primeiro; para mudanças de aspeto, ver capturas (`tools/capturar.py`); nunca fazer `git push` sem o utilizador pedir (regra global); fazer `git pull` antes de mexer, porque o bot atualiza `data/` todos os dias.

Pendente, por ordem de interesse: (1) ver a página num telemóvel real; (2) pesquisa por canal (filtro por emissão, precisa de desenho); (3) poda de `matches` (adiada); (4) exportar/importar as marcas.

## Convenções

- Python 3, dependências apenas `requests` e `beautifulsoup4`.
- Nunca colocar chaves no código; usar variáveis de ambiente.
- Não aumentar a frequência de pedidos ao tudonumclick.com sem motivo.
- Código e comentários em português, como já está.
- Ao descrever resultados ou limitações, preferir linguagem calibrada ("parece", "não verificado") a afirmações definitivas quando não foi testado.
