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

