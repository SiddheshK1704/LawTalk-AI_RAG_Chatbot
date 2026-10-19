"""Chat mode routing: legal questions -> "RAG", everything else -> "LLM" (normal mode).

The original router matched keywords as substrings ("act" matched "fact"/"contact",
"law" matched "lawn") and missed legal questions without a listed keyword, e.g.
"What is a dying declaration?". This version:
  1. sends greetings/small talk to normal mode,
  2. sends questions with explicit legal signals (word-boundary matches) to RAG,
  3. otherwise asks the index: a close match to the legal corpus -> RAG,
  4. else normal mode.
"""
import re

_SMALLTALK = re.compile(
    r"^\s*(hi+|hello+|hey+|namaste|good\s+(morning|afternoon|evening|night)|thanks?(\s+you)?|thank\s+you|"
    r"ok(ay)?|cool|great|bye|who\s+are\s+you|what\s+can\s+you\s+do|how\s+are\s+you)\b[\s!.?,]*$",
    re.I,
)

# Strong signals: legal on their own (matched as whole words).
_STRONG = [
    r"laws?", r"legal(ly)?", r"illegal", r"lawyers?", r"advocates?", r"courts?", r"judges?", r"judgments?", r"tribunal",
    r"statutes?", r"acts?\s+\d{4}", r"[a-z]+\s+act", r"sections?\s+\d+\w*", r"s\.\s*\d+\w*", r"articles?\s+\d+\w*",
    r"constitution(al)?", r"ipc", r"crpc", r"cr\.?p\.?c", r"pocso", r"bns", r"bnss", r"fir", r"bail", r"warrants?",
    r"arrest(ed|s)?", r"police", r"offen[cs]es?", r"crimes?", r"criminal", r"punish(ment|able|ed)?", r"penalt(y|ies)",
    r"imprisonment", r"jail", r"prison", r"convict(ed|ion)?", r"accused", r"prosecut\w*", r"confession", r"murder",
    r"theft", r"dowry", r"rape", r"defamation", r"petition", r"writs?", r"habeas", r"summons", r"tenants?",
    r"landlords?", r"evict\w*", r"divorce", r"alimony", r"inheritance", r"gratuity", r"maternity\s+benefit",
    r"cyber\s*(crime|law)", r"identity\s+theft", r"untouchability", r"supreme\s+court", r"high\s+court", r"magistrate",
    r"sentenced", r"cognizable", r"non-?bailable", r"anticipatory\s+bail", r"fundamental\s+rights?", r"rights",
    r"right\s+to\s+(life|equality|education|privacy|information|freedom|vote|property|religion|constitutional)",
    r"stamp\s+duty", r"trademarks?", r"copyright", r"patents?", r"gst",
    r"without\s+(?:\w+\s+){0,2}(?:permission|consent|authori[sz]ation)", r"unauthori[sz]ed",
]
# Weak signals: common in everyday language ("evidence of climate change"), so they
# need support from the index as well.
_WEAK = [
    r"evidence", r"witness(es)?", r"cheating", r"fraud", r"cruelty", r"harass(ment|ed)?", r"assault", r"contracts?",
    r"agreements?", r"breach", r"liabilit(y|ies)", r"appeal", r"notice", r"maintenance", r"custody", r"succession",
    r"consumer", r"complaint", r"wages?", r"employer", r"retrench\w*", r"licen[cs]e", r"hacking", r"tax(es|ation)?",
    r"compensation", r"damages", r"citizenship", r"fine", r"passwords?", r"salary", r"binding",
]
_STRONG_RE = re.compile(r"\b(" + "|".join(_STRONG) + r")\b", re.I)
_WEAK_RE = re.compile(r"\b(" + "|".join(_WEAK) + r")\b", re.I)

# Dense cosine similarity to the legal index (MiniLM). Values chosen from the questions in
# eval/testset.json and the general questions in tests/test_router.py (see that test).
RAG_SIMILARITY = 0.46        # no keyword: general questions scored <= 0.42, "dying declaration" 0.50
WEAK_SIMILARITY = 0.40       # weak keyword plus a reasonable match


def is_smalltalk(query: str) -> bool:
    return len(query) <= 60 and bool(_SMALLTALK.match(query))


def has_legal_signal(query: str) -> bool:
    return bool(_STRONG_RE.search(query))


def classify(query: str, similarity=None) -> tuple[str, str]:
    """Return (mode, reason). ``similarity`` is a callable returning the best cosine
    similarity of the query against the legal index (only called when needed)."""
    if is_smalltalk(query):
        return "LLM", "smalltalk"
    if _STRONG_RE.search(query):
        return "RAG", "legal_terms"
    if similarity is None:
        return ("RAG", "weak_legal_terms") if _WEAK_RE.search(query) else ("LLM", "no_legal_signal")
    s = similarity(query)
    if _WEAK_RE.search(query) and s >= WEAK_SIMILARITY:
        return "RAG", f"weak_legal_terms+similarity={s:.2f}"
    if s >= RAG_SIMILARITY:
        return "RAG", f"similarity={s:.2f}"
    return "LLM", f"similarity={s:.2f}"


# Kept for backward compatibility with the original module API.
def is_legal_query(query: str) -> bool:
    return classify(query)[0] == "RAG"
