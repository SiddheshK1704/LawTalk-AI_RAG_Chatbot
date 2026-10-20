# LawTalk evaluation results

Run: 2026-10-20 15:05:16  
Config: `{"judge_models": {"faithfulness": "qwen/qwen3.8-27b", "context_recall": "qwen/qwen3.8-27b", "answer_relevancy": "openai/gpt-oss-20b", "context_precision": "openai/gpt-oss-20b", "citation_correctness": "qwen/qwen3.8-27b"}, "testset": "eval/testset.json", "n_questions": 25, "transport": "in-process (no HTTP/auth)"}`

| Metric | Value | Notes |
|---|---|---|
| Faithfulness | 0.901 | RAGAS, scored 20/20 answers |
| Answer relevancy | 0.834 | RAGAS, scored 20/20 answers |
| Context precision | 0.686 | RAGAS, scored 20/20 answers |
| Context recall | 0.825 | RAGAS, scored 20/20 answers |
| Retrieval Recall@5 | 0.710 | labelled chunk IDs, n=20 |
| Retrieval Hit@5 | 0.850 | >=1 labelled chunk in top 5 |
| Citation correctness | 0.684 | LLM judge, 19 citations in 10 answers |
| Unanswerable declined | 0.800 | keyword heuristic, 5/5 answered |
| TTFT p50 (s) | 0.589 | streamed answers, n=25 |
| p95 latency (s) | 60.107 | 50 requests, in-process |
| Request error rate | 0.000 | all failures: {} |
| App error rate | 0.000 | failures not caused by provider limits |
| Provider rate-limited | 0.000 | Groq 429s that survived retries and pacing |
| Routed to RAG | 25/25 | all 25 test questions are legal |

## Latency before / after

| Metric | Before | After | Change |
|---|---|---|---|
| p50 latency (s) | 2.863 | 48.825 | +1605% |
| p95 latency (s) | 11.731 | 60.107 | +412% |
| mean latency (s) | 4.512 | 30.870 | +584% |
| error rate | 0.200 | 0.000 | -100% |

## Caveats

- Reference answers and relevance labels were drafted by an AI assistant from the indexed text and have not been reviewed by a lawyer.
- 25 questions: small-sample metrics, useful for regressions rather than absolute claims.
- LLM-judged metrics (RAGAS, citation correctness) depend on the judge model and can vary between runs.
- Latency depends on the Groq free tier (8K tokens/minute); the client paces requests to stay under it.
- The latency benchmark runs first and alone; quality metrics run afterwards.
- In-process run: same router, retrieval, prompt and Groq code as the API, without HTTP or the auth check.
