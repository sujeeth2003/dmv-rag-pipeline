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

