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

## Pieces
- **ETL (`ragpipe/etl.py`):** parses pages into records (`id, state, section, title, text, updated`), raising a `SchemaError` **with the line number** on malformed input, duplicate ids or empty bodies. `load` writes one JSON file per `(state, section)` partition. `LocalStore` and `S3Store` share an interface; S3 uses boto3 with credentials from the environment/IAM role only.
- **Hierarchy:** the partition path *is* the index. A question that mentions a state and a topic only touches that partition's small index.
- **Retrieval (`ragpipe/retrieval.py`):** BM25 written from scratch (title boosted, state/section searchable) and a **router**: states by name, sections by a data-driven vocabulary (how concentrated each word is in each section).
- **Cache:** an LRU + TTL cache with the `get`/`set` shape of Redis, so `redis.Redis` can replace it for a shared cache.
- **RAG (`ragpipe/rag.py`):** builds a grounded prompt ("answer ONLY from the numbered context, cite rule ids, say so if the answer is not there"). With no API key it answers **extractively** (the best rule's text + citation), so it works offline; pass `anthropic_llm()` (needs `ANTHROPIC_API_KEY`) for fluent multi-rule answers. Low-scoring retrievals return "I don't have that information" instead of guessing.

