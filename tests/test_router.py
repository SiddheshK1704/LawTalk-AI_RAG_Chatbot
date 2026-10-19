"""Mode routing: legal questions -> RAG, general questions -> normal LLM mode."""
import json
from pathlib import Path

from _support import needs_index

from app.services.router import classify

TESTSET = json.loads((Path(__file__).resolve().parents[1] / "eval" / "testset.json").read_text(encoding="utf-8"))
LEGAL = [i["question"] for i in TESTSET]

GENERAL = [
    "Write a Python function to reverse a list",
    "What is the capital of France?",
    "Explain photosynthesis in simple terms",
    "Give me a recipe for pasta carbonara",
    "Who won the 2023 Cricket World Cup?",
    "How do I improve my resume?",
    "Translate good morning into Hindi",
    "What is machine learning?",
    "Tell me a joke",
    "Summarise the plot of Hamlet",
    "What is the evidence for climate change?",          # weak legal word, general meaning
    "Fix the grammar in this sentence: he go to school",  # "sentence"
    "How do I file my nails properly?",                   # "file"
    "What are some tips for a job interview?",
    "How does compound interest work?",
    "What is the boiling point of water?",
    "Recommend a good book on history",
    "Explain how a car engine works",
    "What should I pack for a trip to Goa?",
    "How can I improve my sleep?",
]


def test_smalltalk_is_normal_mode():
    for q in ("hi", "Hello!", "thanks", "who are you?"):
        assert classify(q)[0] == "LLM", q


def test_explicit_legal_terms_route_to_rag_without_index():
    for q in ("What is the punishment for theft?", "Explain Section 420 IPC", "What does Article 21 provide?",
              "Can police arrest without a warrant?", "Is it legal to record a call without consent?"):
        assert classify(q)[0] == "RAG", q


def test_substring_false_positives_fixed():
    # The original router matched "act" in "fact"/"contact" and "law" in "lawn".
    for q in ("Fun fact about cats", "How do I contact support?", "How often should I mow my lawn?"):
        assert classify(q)[0] == "LLM", q


@needs_index
def test_all_legal_test_questions_use_rag(rag):
    misrouted = [q for q in LEGAL if classify(q, rag.max_similarity)[0] != "RAG"]
    assert not misrouted, misrouted


@needs_index
def test_general_questions_use_normal_mode(rag):
    misrouted = [q for q in GENERAL if classify(q, rag.max_similarity)[0] != "LLM"]
    assert not misrouted, misrouted


@needs_index
def test_legal_question_without_keywords_uses_rag(rag):
    # No listed keyword, but close to the corpus.
    assert classify("What is a dying declaration?", rag.max_similarity)[0] == "RAG"
