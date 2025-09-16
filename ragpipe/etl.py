"""ETL: raw text -> validated JSON records -> hive-partitioned object store (S3-compatible interface).

Partition layout   <bucket>/state=<State>/section=<Section>/rules.json
The partition path IS the hierarchy: a query that knows the state and section reads one small file instead of scanning everything.
`LocalStore` writes to disk; `S3Store` (needs boto3 and AWS credentials from the environment, never from code) has the same interface.
"""
import json
import os
import re

RULE_RE = re.compile(r"^RULE\s+([A-Z]{2}-\d+):\s*(.+)$")


class SchemaError(ValueError):
    pass


def extract(raw_text):
    """Parse one state page into records. Raises SchemaError with the line number on malformed input."""
    state = section = rule = None
    recs, body = [], []

    def flush(upd=None):
        nonlocal rule, body
        if rule:
            rule["text"] = " ".join(b.strip() for b in body if b.strip())
            if not rule["text"]:
                raise SchemaError(f"rule {rule['id']} has no body")
            if upd: rule["updated"] = upd
            recs.append(rule)
        rule, body = None, []

