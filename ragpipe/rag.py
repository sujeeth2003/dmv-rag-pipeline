"""RAG answer step. Retrieval -> a grounded prompt -> an LLM (optional) -> an answer that ALWAYS cites its sources.

With no API key the answerer is extractive: it returns the best-matching rule text with its citation, so the pipeline
is fully usable offline and the LLM is a drop-in improvement (fluent multi-rule synthesis), never a requirement.
The LLM is instructed to answer only from the context and to say so when the context does not contain the answer.
"""
import os

from .retrieval import TTLCache

SYSTEM = ("You answer questions about state motor-vehicle and hospital facility rules using ONLY the numbered context below. "
          "Cite rule ids in square brackets. If the context does not contain the answer, say you do not have it. Never guess figures.")


def build_prompt(question, hits):
    ctx = "\n".join(f"[{h['id']}] ({h['state']} / {h['section']}) {h['title']}: {h['text']}" for _, h in hits)
    return f"Context:\n{ctx}\n\nQuestion: {question}\nAnswer:"


class Answerer:
    def __init__(self, index, cache=None, llm=None, min_score=1.0):
        self.index, self.cache, self.llm, self.min_score = index, cache or TTLCache(), llm, min_score

    def answer(self, question, k=3):
        key = question.strip().lower()
        cached = self.cache.get(key)
        if cached:
            return {**cached, "cached": True}
        hits, route = self.index.search(question, k)
        if not hits or hits[0][0] < self.min_score:
            out = {"answer": "I don't have that information in the loaded rules.", "sources": [], "route": route}
        else:
            top = hits[0][1]
            if self.llm:
                text = self.llm(SYSTEM, build_prompt(question, hits))
            else:
                text = f"{top['title']} ({top['state']}): {top['text']}"
            out = {"answer": text, "sources": [{"id": h["id"], "state": h["state"], "section": h["section"], "score": round(s, 2)} for s, h in hits],
                   "route": route}
        self.cache.set(key, out)
        return {**out, "cached": False}


def anthropic_llm(model="claude-sonnet-5"):
    """Optional LLM callable. Needs `pip install anthropic` and ANTHROPIC_API_KEY in the environment."""
    import anthropic
    client = anthropic.Anthropic()

    def call(system, prompt):
        r = client.messages.create(model=model, max_tokens=400, system=system, messages=[{"role": "user", "content": prompt}])
        return r.content[0].text
    return call
