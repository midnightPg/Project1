"""Interface de linha de comandos.

Exemplos:
    python -m horror_bot scrape
    python -m horror_bot scrape -s nosleep shortscarystories --sort top -t month --min-score 500
    python -m horror_bot watch --interval 30
    python -m horror_bot list --top 10
    python -m horror_bot export historias.json
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from .config import DEFAULT_SUBREDDITS, VALID_SORTS, VALID_TIME_FILTERS, Config
from .scraper import HorrorScraper
from .storage import StoryDB, export_json


def _add_scrape_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-s", "--subreddits", nargs="+", default=DEFAULT_SUBREDDITS,
                   help="subreddits a recolher (por defeito: lista de horror)")
    p.add_argument("--sort", choices=VALID_SORTS, default="top")
    p.add_argument("-t", "--time", dest="time_filter", choices=VALID_TIME_FILTERS,
                   default="week", help="período para --sort top")
    p.add_argument("-n", "--limit", type=int, default=50, help="posts por subreddit")
    p.add_argument("--min-score", type=int, default=50)
    p.add_argument("--min-words", type=int, default=300)
    p.add_argument("--no-nsfw", action="store_true", help="excluir posts NSFW")
    p.add_argument("-k", "--keywords", nargs="+", default=[],
                   help="só guardar histórias com uma destas palavras")
    p.add_argument("-o", "--output-dir", default="stories",
                   help="pasta para os ficheiros .md")
    p.add_argument("--no-files", action="store_true", help="não exportar ficheiros .md")


def _config_from_args(args: argparse.Namespace) -> Config:
    return Config(
        subreddits=args.subreddits, sort=args.sort, time_filter=args.time_filter,
        limit_per_subreddit=args.limit, min_score=args.min_score, min_words=args.min_words,
        include_nsfw=not args.no_nsfw, keywords=args.keywords, db_path=args.db,
        output_dir=args.output_dir,
    )


def _print_stats(stats) -> None:
    print(f"\nVistos: {stats.seen} | Novos: {stats.new} | Já existentes: {stats.updated}")
    if stats.rejected:
        print("Rejeitados: " + ", ".join(f"{k}={v}" for k, v in stats.rejected.items()))
    for sub, err in stats.errors.items():
        print(f"ERRO r/{sub}: {err}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="horror_bot",
                                     description="Recolhe histórias de horror do Reddit.")
    parser.add_argument("--db", default="horror_stories.db", help="ficheiro SQLite")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scrape = sub.add_parser("scrape", help="recolher uma vez")
    _add_scrape_args(p_scrape)

    p_watch = sub.add_parser("watch", help="recolher continuamente")
    _add_scrape_args(p_watch)
    p_watch.add_argument("--interval", type=float, default=60, help="minutos entre recolhas")

    p_list = sub.add_parser("list", help="listar histórias guardadas")
    p_list.add_argument("--top", type=int, default=20)
    p_list.add_argument("--subreddit")

    p_export = sub.add_parser("export", help="exportar a base de dados para JSON")
    p_export.add_argument("path")
    p_export.add_argument("--subreddit")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    if args.cmd in ("scrape", "watch"):
        scraper = HorrorScraper(_config_from_args(args))
        while True:
            stats, _ = scraper.run_once(export=not args.no_files)
            _print_stats(stats)
            if args.cmd == "scrape":
                return 1 if stats.errors and not stats.seen else 0
            print(f"Próxima recolha daqui a {args.interval:g} min (Ctrl+C para parar).")
            try:
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                return 0

    db = StoryDB(args.db)
    if args.cmd == "list":
        stories = db.all(args.subreddit)[: args.top]
        for s in stories:
            print(f"[{s.score:>6}] r/{s.subreddit:<20} {s.title}  ({s.word_count} palavras)")
        print(f"\nTotal na base de dados: {db.count()}")
    elif args.cmd == "export":
        out = export_json(db.all(args.subreddit), args.path)
        print(f"Exportado para {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
