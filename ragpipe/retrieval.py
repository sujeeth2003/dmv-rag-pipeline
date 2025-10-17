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

