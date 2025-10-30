import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ragpipe import etl  # noqa: E402
from ragpipe.rag import Answerer, build_prompt  # noqa: E402
from ragpipe.retrieval import BM25, HierarchicalIndex, TTLCache, load_index_from_store  # noqa: E402
from ragpipe.sample_data import make_pages  # noqa: E402


class ETLTests(unittest.TestCase):
    def test_extract_parses_all_fields(self):
        recs = etl.extract(make_pages(seed=1)["Northvale"])
        self.assertGreater(len(recs), 10)
        r = recs[0]
        self.assertEqual((r["state"], r["section"]), ("Northvale", "Vehicle Registration"))
        self.assertTrue(r["id"].startswith("NO-") and r["text"] and r["updated"])

    def test_malformed_input_reports_line(self):
        with self.assertRaises(etl.SchemaError) as e: etl.extract("RULE NV-1: orphan\nbody\n")
        self.assertIn("line 1", str(e.exception))
        with self.assertRaises(etl.SchemaError): etl.extract("STATE: X\nSECTION: Y\nRULE XX-1: t\nRULE XX-2: t2\nbody\n")   # empty body

    def test_partitioned_load_roundtrip(self):
        st = etl.LocalStore(tempfile.mkdtemp())
        recs = [r for p in make_pages(1).values() for r in etl.extract(p)]
        keys = etl.load(recs, st)
        self.assertEqual(len(keys), 8 * 4)                            # states x sections
        self.assertTrue(all(k.startswith("state=") and "/section=" in k for k in keys))
        self.assertEqual(sum(len(json.loads(st.get(k))) for k in keys), len(recs))


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = etl.LocalStore(tempfile.mkdtemp())
        cls.recs = [r for p in make_pages(2, rules_per_section=5).values() for r in etl.extract(p)]
        etl.load(cls.recs, st)
        cls.idx = load_index_from_store(st)

    def test_bm25_ranks_the_matching_doc_first(self):
        docs = [{"id": "1", "title": "Bicycle helmets", "text": "must be worn"}, {"id": "2", "title": "Truck weight", "text": "limits apply"}]
        self.assertEqual(BM25(docs).search("weight limits for a truck", 1)[0][1]["id"], "2")

    def test_router_finds_state_and_section(self):
        states, secs = self.idx.route("hospital inspection frequency in Eastmoor")
        self.assertEqual(states, ["Eastmoor"]); self.assertIn("Hospital Facility Codes", secs)

    def test_hierarchical_matches_flat_accuracy_and_scans_fewer_docs(self):
        hits = 0
        gold = self.recs[::37][:40]
        for g in gold:
            q = f"{g['title'].split(' (')[0]} in {g['state']} {g['title'].split('schedule ')[-1].rstrip(')')}"
            h, route = self.idx.search(q, 3, hierarchical=True)
            hits += g["id"] in [x["id"] for _, x in h]
            self.assertLess(route["partitions"], len(self.idx.parts))         # routed to a strict subset of partitions
        self.assertGreaterEqual(hits / len(gold), 0.7)

    def test_cache_ttl_and_lru(self):
        t = [0.0]; c = TTLCache(capacity=2, ttl=10, clock=lambda: t[0])
        c.set("a", 1); c.set("b", 2); c.set("c", 3)
        self.assertIsNone(c.get("a"))                                        # evicted (LRU)
        self.assertEqual(c.get("c"), 3)
        t[0] = 11; self.assertIsNone(c.get("c"))                             # expired (TTL)


class RagTests(unittest.TestCase):
    def setUp(self):
        recs = [r for p in make_pages(3).values() for r in etl.extract(p)]
        self.bot = Answerer(HierarchicalIndex(recs))

    def test_answer_cites_sources_and_caches(self):
        r1 = self.bot.answer("What is the licence renewal period in Northvale?")
        self.assertTrue(r1["sources"]); self.assertFalse(r1["cached"]); self.assertIn("Northvale", r1["answer"])
        self.assertTrue(self.bot.answer("What is the licence renewal period in Northvale?")["cached"])

    def test_refuses_when_nothing_relevant(self):
        r = self.bot.answer("What is the airspeed velocity of an unladen swallow?")
        self.assertEqual(r["sources"], []); self.assertIn("don't have", r["answer"])

