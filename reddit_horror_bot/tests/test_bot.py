"""Testes offline: a API do Reddit é simulada."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from horror_bot.__main__ import main
from horror_bot.client import RedditClient
from horror_bot.config import Config
from horror_bot.scraper import HorrorScraper
from horror_bot.storage import StoryDB

LONG_BODY = " ".join(["escuro"] * 400)


def post(id_, score=1000, body=LONG_BODY, **extra):
    data = {
        "id": id_, "subreddit": "nosleep", "title": f"História {id_}", "author": "autor",
        "selftext": body, "score": score, "num_comments": 10,
        "permalink": f"/r/nosleep/comments/{id_}/x/", "created_utc": 1700000000,
        "is_self": True, "over_18": False, "stickied": False, "link_flair_text": None,
    }
    data.update(extra)
    return {"kind": "t3", "data": data}


def listing(children, after=None):
    return {"kind": "Listing", "data": {"children": children, "after": after}}


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        return self.responses.pop(0)

    def post(self, url, **kw):
        self.calls.append((url, kw.get("data")))
        return FakeResponse({"access_token": "tok", "expires_in": 3600})


def make_client(config, responses):
    return RedditClient(config, session=FakeSession(responses), sleep=lambda s: None)


class BotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.config = Config(subreddits=["nosleep"], limit_per_subreddit=10,
                             db_path=str(self.dir / "db.sqlite"),
                             output_dir=str(self.dir / "out"),
                             client_id=None, client_secret=None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_filters_and_saves(self):
        children = [
            post("ok1"),
            post("low", score=3),
            post("short", body="curta demais"),
            post("removed", body="[removed]"),
            post("pinned", stickied=True),
            post("meta", link_flair_text="Meta"),
            post("link", is_self=False),
        ]
        client = make_client(self.config, [FakeResponse(listing(children))])
        stats, new = HorrorScraper(self.config, client=client).run_once()
        self.assertEqual([s.id for s in new], ["ok1"])
        self.assertEqual(stats.seen, 7)
        self.assertEqual(sum(stats.rejected.values()), 6)
        files = list((self.dir / "out" / "nosleep").glob("*.md"))
        self.assertEqual(len(files), 1)
        self.assertIn("História ok1", files[0].read_text(encoding="utf-8"))

    def test_deduplicates_between_runs(self):
        responses = [FakeResponse(listing([post("a")])),
                     FakeResponse(listing([post("a", score=2000)]))]
        client = make_client(self.config, responses)
        scraper = HorrorScraper(self.config, client=client)
        self.assertEqual(scraper.run_once()[0].new, 1)
        stats, _ = scraper.run_once()
        self.assertEqual((stats.new, stats.updated), (0, 1))
        self.assertEqual(scraper.db.all()[0].score, 2000)

    def test_pagination_and_params(self):
        self.config.limit_per_subreddit = 3
        responses = [FakeResponse(listing([post("a"), post("b")], after="t3_b")),
                     FakeResponse(listing([post("c"), post("d")]))]
        client = make_client(self.config, responses)
        ids = [p["id"] for p in client.iter_posts("nosleep", "top", 3, "month")]
        self.assertEqual(ids, ["a", "b", "c"])
        url, params = client.session.calls[1]
        self.assertEqual(url, "https://www.reddit.com/r/nosleep/top.json")
        self.assertEqual(params["after"], "t3_b")
        self.assertEqual(params["t"], "month")
        self.assertEqual(params["limit"], 1)

    def test_retries_on_429(self):
        responses = [FakeResponse({}, status=429, headers={"Retry-After": "1"}),
                     FakeResponse(listing([post("a")]))]
        client = make_client(self.config, responses)
        self.assertEqual(len(list(client.iter_posts("nosleep", "new", 5))), 1)

    def test_oauth_mode(self):
        self.config.client_id, self.config.client_secret = "id", "secret"
        client = make_client(self.config, [FakeResponse(listing([post("a")]))])
        list(client.iter_posts("nosleep", "hot", 5))
        self.assertEqual(client.session.headers["Authorization"], "bearer tok")
        self.assertEqual(client.session.calls[1][0], "https://oauth.reddit.com/r/nosleep/hot")

    def test_subreddit_error_does_not_stop_run(self):
        self.config.subreddits = ["banido", "nosleep"]
        responses = [FakeResponse({}, status=404), FakeResponse(listing([post("a")]))]
        client = make_client(self.config, responses)
        stats, new = HorrorScraper(self.config, client=client).run_once()
        self.assertIn("banido", stats.errors)
        self.assertEqual(len(new), 1)

    def test_keywords(self):
        self.config.keywords = ["fantasma"]
        children = [post("a"), post("b", body=LONG_BODY + " um fantasma")]
        client = make_client(self.config, [FakeResponse(listing(children))])
        _, new = HorrorScraper(self.config, client=client).run_once(export=False)
        self.assertEqual([s.id for s in new], ["b"])

    def test_cli_list_and_export(self):
        db = StoryDB(self.config.db_path)
        client = make_client(self.config, [FakeResponse(listing([post("a")]))])
        HorrorScraper(self.config, client=client, db=db).run_once(export=False)
        out = self.dir / "out.json"
        with mock.patch("sys.stdout"):
            self.assertEqual(main(["--db", self.config.db_path, "export", str(out)]), 0)
            self.assertEqual(main(["--db", self.config.db_path, "list"]), 0)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data[0]["id"], "a")
        self.assertEqual(data[0]["word_count"], 400)


if __name__ == "__main__":
    unittest.main()
