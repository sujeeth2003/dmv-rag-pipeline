"""End to end: generate raw pages -> ETL into a partitioned store -> index -> ask questions -> measure routing.

    python run_pipeline.py [--scale 25]        # scale multiplies the corpus size for the latency benchmark
"""
import argparse
import random
import tempfile
import time

from ragpipe import etl
from ragpipe.rag import Answerer
from ragpipe.retrieval import load_index_from_store
from ragpipe.sample_data import make_pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=25)
    a = ap.parse_args()

    store = etl.LocalStore(tempfile.mkdtemp(prefix="ragstore-"))
    pages = make_pages(seed=1, rules_per_section=a.scale)
    t0 = time.time()
    records = [r for p in pages.values() for r in etl.extract(p)]
    keys = etl.load(records, store)
    print(f"ETL: {len(pages)} pages -> {len(records)} validated records -> {len(keys)} partitions in {time.time() - t0:.2f}s")
    print("  e.g.", keys[0])
    idx = load_index_from_store(store)

