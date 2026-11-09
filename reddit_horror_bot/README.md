# 👻 Reddit Horror Bot

Bot em Python que recolhe histórias de horror do Reddit (r/nosleep, r/shortscarystories,
r/LetsNotMeet, r/Glitch_in_the_Matrix, ...). Filtra por qualidade e guarda tudo numa base
de dados SQLite (sem duplicados) e em ficheiros Markdown, um por história.

## Instalação

```bash
cd reddit_horror_bot
pip install -r requirements.txt
```

## Utilização

```bash
# Recolher uma vez (top da semana, subreddits por defeito)
python -m horror_bot scrape

# Escolher subreddits, período e score mínimo
python -m horror_bot scrape -s nosleep shortscarystories --sort top -t month --min-score 500

# Só histórias com certas palavras, sem NSFW
python -m horror_bot scrape -k fantasma ghost demon --no-nsfw

# Modo bot: recolhe de 30 em 30 minutos (Ctrl+C para parar)
python -m horror_bot watch --sort new --interval 30

# Ver as melhores histórias guardadas
python -m horror_bot list --top 10

# Exportar tudo para JSON
python -m horror_bot export historias.json
```

Resultado:
- `horror_stories.db` — base de dados SQLite (`--db` para mudar o caminho)
- `stories/<subreddit>/<id>-<titulo>.md` — uma história por ficheiro (`-o` para mudar a pasta, `--no-files` para desligar)

### Filtros aplicados
Posts fixados, links (não texto), removidos/apagados, flairs de meta/anúncios, score abaixo
de `--min-score` (50) e textos com menos de `--min-words` (300) palavras são ignorados.

## Credenciais (recomendado)

Sem credenciais o bot usa os endpoints públicos `.json`, limitados a ~10 pedidos/min
(o bot espera 6 s entre pedidos e repete automaticamente em caso de HTTP 429/5xx).
O Reddit bloqueia cada vez mais pedidos anónimos, por isso o ideal é criar uma app:

1. Vai a <https://www.reddit.com/prefs/apps> → **create app** → tipo **script**.
2. Define as variáveis de ambiente:

```bash
export REDDIT_CLIENT_ID="o_teu_client_id"
export REDDIT_CLIENT_SECRET="o_teu_secret"
export REDDIT_USER_AGENT="python:horror-story-bot:v1.0 (by u/o_teu_utilizador)"
```

Com isto o bot passa a usar `oauth.reddit.com` automaticamente.

## Usar como biblioteca

```python
from horror_bot import Config, HorrorScraper

stats, novas = HorrorScraper(Config(subreddits=["nosleep"], min_score=1000)).run_once()
for s in novas:
    print(s.title, s.url)
```

## Testes

```bash
python -m unittest discover -s tests -t .
```

## Aviso

As histórias pertencem aos seus autores. Respeita os
[termos da API do Reddit](https://www.redditinc.com/policies/data-api-terms) e pede
autorização ao autor antes de republicar (ex.: narrações no YouTube).
