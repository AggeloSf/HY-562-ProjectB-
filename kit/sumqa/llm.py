"""LLM back-ends with a disk cache and a spending cap.

  ollama:<model>      local model through Ollama, e.g. ollama:qwen2.5-coder:7b
                      (OLLAMA_HOST, default http://localhost:11434; from the course
                      container use http://host.docker.internal:11434)
  openai:<model>      any OpenAI-compatible API (OPENAI_BASE_URL, OPENAI_API_KEY);
                      cost is tracked with --price-in / --price-out (USD per 1M tokens)
                      and the run stops when cache/spend.json reaches SUMQA_MAX_USD
  mock:gold           returns the gold query (pipeline tests only)
  mock:noisy          returns the gold query with one property replaced, every second time

Generation is deterministic (temperature 0) and cached by (model, prompt), so a
rerun of the same setting costs nothing.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

from .cache import DiskCache
from .common import sha


class BudgetExceeded(Exception):
    pass


class LLM:
    def __init__(self, spec: str, cache_dir: str = "cache/llm", price_in: float = 0.0, price_out: float = 0.0,
                 num_ctx: int = 8192):
        self.spec = spec
        self.kind, _, self.model = spec.partition(":")
        self.price_in, self.price_out, self.num_ctx = price_in, price_out, num_ctx
        os.makedirs(cache_dir, exist_ok=True)
        self.cache = DiskCache(os.path.join(cache_dir, re.sub(r"[^A-Za-z0-9_.-]", "_", spec) + ".sqlite"))
        self.spend_file = os.path.join(cache_dir, "spend.json")
        self.max_usd = float(os.environ.get("SUMQA_MAX_USD", "0") or 0)

    def close(self):
        self.cache.close()

    def generate(self, system: str, user: str, record: dict | None = None) -> dict:
        """Returns {"text", "prompt_tokens", "completion_tokens", "seconds", "cached"}."""
        key = sha(self.spec + "\n" + system + "\n" + user)
        hit = self.cache.get(key) if self.kind != "mock" else None
        if hit is not None:
            return {**hit, "cached": True}
        t0 = time.time()
        if self.kind == "ollama":
            out = self._ollama(system, user)
        elif self.kind == "openai":
            out = self._openai(system, user)
        elif self.kind == "mock":
            out = self._mock(record or {})
        else:
            raise ValueError(f"unknown model spec {self.spec}")
        out["seconds"] = round(time.time() - t0, 3)
        if self.kind != "mock":
            self.cache.put(key, out)
        return {**out, "cached": False}

    # ------------------------------------------------------------ back-ends
    def _ollama(self, system, user):
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        r = requests.post(f"{host}/api/chat", timeout=600, json={
            "model": self.model, "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0, "seed": 562, "num_ctx": self.num_ctx}})
        r.raise_for_status()
        js = r.json()
        return {"text": js["message"]["content"], "prompt_tokens": js.get("prompt_eval_count"),
                "completion_tokens": js.get("eval_count")}

    def _openai(self, system, user):
        spent = self._spent()
        if self.max_usd and spent >= self.max_usd:
            raise BudgetExceeded(f"spent {spent:.2f} USD of {self.max_usd:.2f}")
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        r = requests.post(f"{base}/chat/completions", timeout=600,
                          headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                          json={"model": self.model, "temperature": 0,
                                "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": user}]})
        r.raise_for_status()
        js = r.json()
        u = js.get("usage", {})
        pin, pout = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        self._add_spend((pin * self.price_in + pout * self.price_out) / 1e6)
        return {"text": js["choices"][0]["message"]["content"], "prompt_tokens": pin, "completion_tokens": pout}

    def _mock(self, rec):
        q = rec.get("sparql", "SELECT * WHERE { ?s ?p ?o } LIMIT 1")
        if self.model == "noisy" and int(sha(rec.get("id", "")), 16) % 2:
            q = re.sub(r"(ontology/|ex:|dbo:)([a-z]\w*)", r"\1wrong\2", q, count=1)
        return {"text": f"```sparql\n{q}\n```", "prompt_tokens": None, "completion_tokens": None}

    # ------------------------------------------------------------ spend tracking
    def _spent(self):
        try:
            return json.load(open(self.spend_file)).get("usd", 0.0)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0.0

    def _add_spend(self, usd):
        tot = self._spent() + usd
        with open(self.spend_file, "w") as f:
            json.dump({"usd": round(tot, 6)}, f)


SPARQL_BLOCK = re.compile(r"```(?:sparql|SPARQL)?\s*(.*?)```", re.S)
QUERY_START = re.compile(r"(PREFIX\s|SELECT\s|ASK\s|ASK\{|CONSTRUCT\s|DESCRIBE\s)", re.I)


def extract_sparql(text: str) -> str | None:
    """The query in the first code block, or from the first PREFIX/SELECT/ASK on."""
    m = SPARQL_BLOCK.search(text)
    if m and QUERY_START.search(m.group(1)):
        return m.group(1).strip()
    m = QUERY_START.search(text)
    return text[m.start():].strip() if m else None
