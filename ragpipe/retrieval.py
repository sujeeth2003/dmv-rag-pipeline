"""Retrieval: BM25 (implemented here) with hierarchical routing, and a TTL/LRU cache with a Redis-compatible shape."""
import json
import math
import re
import time
from collections import OrderedDict

TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("the a an of to in is are for and or what how much does do i my on by with be at must may".split())


