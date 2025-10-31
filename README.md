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

## Results (2,200 rules across 8 states x 4 sections = 32 partitions; 200 questions with a known gold rule)
```
retrieval                    top-1   top-3  ms / query
flat BM25 (whole corpus)      100%    100%        2.67
hierarchical (routed)          92%    100%        0.22
```
The hierarchy is **12x faster** because each query scans roughly 70-140 rules instead of 2,200, and it stays at 100% top-3, but **top-1 falls from 100% to 92%**: when the router picks the wrong section the right rule is not a candidate. That is the real trade-off of structuring data for speed. (An earlier version of my comparison showed flat retrieval at 12% only because the index could not see the state name; I fixed that so the baseline is fair.) With real, non-templated text the flat index has less trouble telling rules apart, so expect a smaller accuracy gap and the same latency gain. A cached repeat of a question costs ~3 microseconds.

## Run
```bash
python -m unittest discover -s tests     # 10 tests: parsing + error lines, partitioned load, BM25, routing, cache TTL/LRU, refusal, grounded prompt
python run_pipeline.py                   # ETL, benchmark, three sample questions
```
Pure standard library. Optional: `boto3` (S3), `redis`, `anthropic`. MongoDB fits as the record store in place of JSON files (same records); it is not wired in here.

## Limits
Lexical search only (no embeddings), so paraphrases with no shared words will miss; adding a dense retriever and merging scores is the natural next step. The router assumes the state is named in the question.
