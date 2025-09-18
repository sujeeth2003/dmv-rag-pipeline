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

    for ln, line in enumerate(raw_text.splitlines(), 1):
        s = line.strip()
        if s.startswith("STATE:"): state = s[6:].strip()
        elif s.startswith("SECTION:"): flush(); section = s[8:].strip()
        elif RULE_RE.match(s):
            flush()
            if not (state and section): raise SchemaError(f"line {ln}: rule before STATE/SECTION")
            rid, title = RULE_RE.match(s).groups()
            rule = {"id": rid, "state": state, "section": section, "title": title, "text": "", "updated": None}
        elif s.startswith("Updated:"): flush(s[8:].strip())
        elif rule is not None: body.append(s)
    flush()
    ids = [r["id"] for r in recs]
    if len(ids) != len(set(ids)): raise SchemaError("duplicate rule ids")
    return recs


class LocalStore:
    def __init__(self, root): self.root = root
    def put(self, key, data: bytes):
        p = os.path.join(self.root, key); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f: f.write(data)
    def get(self, key):
        with open(os.path.join(self.root, key), "rb") as f: return f.read()
    def list(self, prefix=""):
        out = []
        for d, _, fs in os.walk(os.path.join(self.root, prefix)):
            out += [os.path.relpath(os.path.join(d, f), self.root).replace("\\", "/") for f in fs]
        return sorted(out)


class S3Store:
    """Same interface over Amazon S3 (credentials come from the standard AWS environment / IAM role)."""
    def __init__(self, bucket):
        import boto3
        self.s3, self.bucket = boto3.client("s3"), bucket
    def put(self, key, data: bytes): self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)
    def get(self, key): return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
    def list(self, prefix=""):
        out = []
        for page in self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            out += [o["Key"] for o in page.get("Contents", [])]
        return sorted(out)

