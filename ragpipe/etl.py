"""ETL: raw text -> validated JSON records -> hive-partitioned object store (S3-compatible interface).

Partition layout   <bucket>/state=<State>/section=<Section>/rules.json
The partition path IS the hierarchy: a query that knows the state and section reads one small file instead of scanning everything.
`LocalStore` writes to disk; `S3Store` (needs boto3 and AWS credentials from the environment, never from code) has the same interface.
"""
import json
import os
import re

RULE_RE = re.compile(r"^RULE\s+([A-Z]{2}-\d+):\s*(.+)$")


