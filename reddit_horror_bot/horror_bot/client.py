"""Cliente HTTP mínimo para a API do Reddit.

Suporta dois modos:
  * Anónimo: usa os endpoints públicos `.json` de www.reddit.com.
  * OAuth "application-only": se REDDIT_CLIENT_ID e REDDIT_CLIENT_SECRET
    estiverem definidos, obtém um token e usa oauth.reddit.com
    (limites mais altos e menos bloqueios).
"""

from __future__ import annotations

import logging
import time
from typing import Iterator

import requests

from .config import Config

log = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
PUBLIC_BASE = "https://www.reddit.com"
OAUTH_BASE = "https://oauth.reddit.com"


class RedditClient:
    def __init__(self, config: Config, session: requests.Session | None = None,
                 sleep=time.sleep, clock=time.monotonic):
        self.config = config
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = config.user_agent
        self._sleep = sleep
        self._clock = clock
        self._last_request = 0.0
        self._token: str | None = None
        self._token_expires = 0.0

    # ---------- autenticação ----------
    @property
    def uses_oauth(self) -> bool:
        return bool(self.config.client_id and self.config.client_secret)

    def _ensure_token(self) -> None:
        if not self.uses_oauth or (self._token and self._clock() < self._token_expires):
            return
        resp = self.session.post(
            TOKEN_URL,
            auth=(self.config.client_id, self.config.client_secret),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expires = self._clock() + int(payload.get("expires_in", 3600)) - 60
        self.session.headers["Authorization"] = f"bearer {self._token}"
        log.info("Token OAuth obtido.")

    # ---------- pedidos ----------
    def _throttle(self) -> None:
        delay = self.config.request_delay if not self.uses_oauth else min(
            self.config.request_delay, 1.0
        )
        wait = self._last_request + delay - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._last_request = self._clock()

    def get_json(self, path: str, params: dict | None = None, max_retries: int = 4) -> dict:
        self._ensure_token()
        if self.uses_oauth:
            url = OAUTH_BASE + path
        else:
            url = PUBLIC_BASE + path + ".json"
        params = {**(params or {}), "raw_json": 1}

        backoff = 2.0
        for attempt in range(max_retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                if attempt == max_retries:
                    raise
                log.warning("Erro de rede (%s), nova tentativa em %.0fs", exc, backoff)
                self._sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == max_retries:
                    resp.raise_for_status()
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else backoff
                log.warning("HTTP %s em %s, a aguardar %.0fs", resp.status_code, path, wait)
                self._sleep(wait)
                backoff *= 2
                continue

            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("inalcançável")

    def iter_posts(self, subreddit: str, sort: str, limit: int,
                   time_filter: str = "week") -> Iterator[dict]:
        """Itera sobre posts (dicts `data`) de um subreddit, com paginação."""
        after = None
        fetched = 0
        while fetched < limit:
            params = {"limit": min(100, limit - fetched)}
            if sort == "top":
                params["t"] = time_filter
            if after:
                params["after"] = after
            listing = self.get_json(f"/r/{subreddit}/{sort}", params)
            children = listing.get("data", {}).get("children", [])
            if not children:
                return
            for child in children:
                if child.get("kind") != "t3":
                    continue
                fetched += 1
                yield child["data"]
                if fetched >= limit:
                    return
            after = listing["data"].get("after")
            if not after:
                return
