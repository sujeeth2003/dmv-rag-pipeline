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

    # questions with a known gold rule: ask about a rule's title, in a given state
    rnd = random.Random(0)
    gold = rnd.sample(records, 200)
    qs = [(f"What is the {g['title'].split(' (')[0].lower()} in {g['state']} (schedule {g['title'].split('schedule ')[-1].rstrip(')')})?", g) for g in gold]

    def evaluate(hier):
        top1 = top3 = 0
        t0 = time.perf_counter()
        for q, g in qs:
            hits, _ = idx.search(q, 3, hierarchical=hier)
            ids = [h["id"] for _, h in hits]
            top1 += bool(ids) and ids[0] == g["id"]; top3 += g["id"] in ids
        return top1 / len(qs), top3 / len(qs), (time.perf_counter() - t0) / len(qs) * 1000
    print(f"\n{'retrieval':<26}{'top-1':>8}{'top-3':>8}{'ms / query':>12}")
    for name, h in (("flat BM25 (whole corpus)", False), ("hierarchical (routed)", True)):
        t1, t3, ms = evaluate(h)
        print(f"{name:<26}{t1:>8.0%}{t3:>8.0%}{ms:>12.2f}")

    bot = Answerer(idx)
    for q in ["What is the licence renewal period in Northvale (schedule 1)?", "How often are hospitals inspected in Eastmoor (schedule 2)?",
              "What is the airspeed of an unladen swallow?"]:
        r = bot.answer(q)
        print(f"\nQ: {q}\nA: {r['answer']}\n   sources: {[s['id'] for s in r['sources']]}  route: {r['route']}")
    t0 = time.perf_counter(); bot.answer("What is the licence renewal period in Northvale (schedule 1)?")
    print(f"\ncached repeat of the first question: {(time.perf_counter() - t0) * 1000:.3f} ms  (cache hits={bot.cache.hits})")


if __name__ == "__main__":
    main()
