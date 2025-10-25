"""RAG answer step. Retrieval -> a grounded prompt -> an LLM (optional) -> an answer that ALWAYS cites its sources.

With no API key the answerer is extractive: it returns the best-matching rule text with its citation, so the pipeline
is fully usable offline and the LLM is a drop-in improvement (fluent multi-rule synthesis), never a requirement.
The LLM is instructed to answer only from the context and to say so when the context does not contain the answer.
"""
import os

from .retrieval import TTLCache

SYSTEM = ("You answer questions about state motor-vehicle and hospital facility rules using ONLY the numbered context below. "
          "Cite rule ids in square brackets. If the context does not contain the answer, say you do not have it. Never guess figures.")


