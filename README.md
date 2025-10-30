# DMV / State-Standards RAG Pipeline

An ETL + retrieval-augmented-generation pipeline for state motor-vehicle and hospital-facility rules: raw pages are extracted into validated JSON, loaded into a **hierarchically partitioned object store** (S3-style), indexed, and answered by a chatbot that **always cites its sources** and refuses when it has no answer.

> **All data here is fictional.** The states, fees, deadlines and rule numbers are generated (`ragpipe/sample_data.py`) so the pipeline is runnable and testable; they are not real regulations and must not be used as such. Point `etl.extract` at real pages of the same shape to use it for real.

```
raw pages --extract/validate--> JSON records --partition--> store: state=<s>/section=<c>/rules.json   (LocalStore or S3Store)
                                                              |
              question --> router (state, section) --> BM25 over only the matching partitions --> top-k rules
                                                              |
                                        cache (TTL/LRU, Redis-shaped) --> answer + citations (extractive, or LLM if configured)
```

