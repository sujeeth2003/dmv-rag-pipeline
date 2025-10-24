"""Retrieval: BM25 (implemented here) with hierarchical routing, and a TTL/LRU cache with a Redis-compatible shape."""
import json
import math
import re
import time
from collections import OrderedDict

TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("the a an of to in is are for and or what how much does do i my on by with be at must may".split())


def tokens(t): return [w for w in TOKEN.findall(t.lower()) if w not in STOP]


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.tf = [self._tf(tokens(d["title"] + " " + d["title"] + " " + d["text"] + " " + d.get("state", "") + " " + d.get("section", ""))) for d in docs]
        # title counted twice: a cheap field boost. State and section are searchable too, so the FLAT index is a fair baseline.
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = (sum(self.len) / len(self.len)) if docs else 1.0
        self.df = {}
        for t in self.tf:
            for w in t: self.df[w] = self.df.get(w, 0) + 1
        self.n = len(docs)

    @staticmethod
    def _tf(ts):
        d = {}
        for w in ts: d[w] = d.get(w, 0) + 1
        return d

    def search(self, query, k=5):
        q = tokens(query)
        scores = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for w in q:
                f = tf.get(w)
                if not f: continue
                idf = math.log(1 + (self.n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s > 0: scores.append((s, i))
        scores.sort(reverse=True)
        return [(s, self.docs[i]) for s, i in scores[:k]]


class HierarchicalIndex:
    """One BM25 index per (state, section) partition plus a flat index over everything.
    A router narrows the query to the states/sections it mentions, so BM25 scans a partition, not the corpus."""

    def __init__(self, records):
        self.records = records
        self.flat = BM25(records)
        self.parts, self.states, self.sections = {}, set(), set()
        for r in records:
            self.parts.setdefault((r["state"], r["section"]), []).append(r)
            self.states.add(r["state"]); self.sections.add(r["section"])
        self.part_idx = {k: BM25(v) for k, v in self.parts.items()}
        # data-driven section vocabulary: how concentrated each word is in each section (1.0 = appears only there)
        self.sec_tf, tot = {s: {} for s in self.sections}, {}
        for r in records:
            for w in set(tokens(r["title"] + " " + r["text"])):
                self.sec_tf[r["section"]][w] = self.sec_tf[r["section"]].get(w, 0) + 1
                tot[w] = tot.get(w, 0) + 1
        self.conc = {s: {w: c / tot[w] for w, c in d.items()} for s, d in self.sec_tf.items()}

    def route(self, query):
        q = set(tokens(query))
        states = [s for s in self.states if q & set(tokens(s))]
        scored = sorted(((sum(self.conc[s].get(w, 0.0) for w in q), s) for s in self.sections), reverse=True)
        secs = [s for sc, s in scored[:2] if sc >= 0.6]          # up to two sections whose vocabulary the query really uses
        return states, secs

    def search(self, query, k=5, hierarchical=True):
        if not hierarchical:
            return self.flat.search(query, k), None
        states, secs = self.route(query)
        cand = [key for key in self.part_idx if (not states or key[0] in states) and (not secs or key[1] in secs)]
        hits = []
        for key in cand:
            hits += self.part_idx[key].search(query, k)      # scores are per-partition BM25; merge by score
        hits.sort(key=lambda x: -x[0])
        return hits[:k], {"states": states, "sections": secs, "partitions": len(cand)}


class TTLCache:
    """LRU + time-to-live cache with the get/set shape of Redis, so `redis.Redis` can be dropped in."""

    def __init__(self, capacity=1024, ttl=300.0, clock=time.monotonic):
        self.cap, self.ttl, self.clock, self.d = capacity, ttl, clock, OrderedDict()
        self.hits = self.misses = 0

    def get(self, key):
        v = self.d.get(key)
        if v is None or v[0] < self.clock():
            self.d.pop(key, None); self.misses += 1; return None
        self.d.move_to_end(key); self.hits += 1
        return v[1]

