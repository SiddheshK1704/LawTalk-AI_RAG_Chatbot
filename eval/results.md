# LawTalk evaluation results

Run: 2026-10-19 14:05:51  
Config: `{"judge_model": "qwen/qwen3.8-27b", "testset": "eval/testset.json", "n_questions": 25, "answer_endpoint": "/ask/stream", "benchmark_endpoint": "/ask"}`

| Metric | Value | Notes |
|---|---|---|
| Faithfulness | 0.594 | RAGAS, scored 13/20 answers |
| Answer relevancy | 0.532 | RAGAS, scored 13/20 answers |
| Context precision | 0.268 | RAGAS, scored 13/20 answers |
| Context recall | 0.346 | RAGAS, scored 13/20 answers |
| Retrieval Recall@5 | 0.317 | labelled chunk IDs, n=20 |
| Retrieval Hit@5 | 0.450 | >=1 labelled chunk in top 5 |
| Citation correctness | 0.500 | LLM judge, 2 citations in 10 answers |
| Unanswerable declined | 1.000 | keyword heuristic, 2/5 answered |
| TTFT p50 (s) | 0.544 | /ask/stream, n=22 |
| p95 latency (s) | 10.793 | 50 requests |
| Request error rate | 0.240 | errors: {'http_503': 12} |

## Latency before / after

| Metric | Before | After | Change |
|---|---|---|---|
| p50 latency (s) | 2.863 | 4.521 | +58% |
| p95 latency (s) | 11.731 | 10.793 | -8% |
| mean latency (s) | 4.512 | 4.440 | -2% |
| error rate | 0.200 | 0.240 | +20% |

## Caveats

- This run hit provider rate/daily limits: 3 answer requests failed, 28 RAGAS metric calls and 18 citation checks could not be judged, and 12 benchmark requests returned errors. Scores cover only what was measured; re-run with fresh quota for complete numbers.
- Reference answers and relevance labels were drafted by an AI assistant from the indexed text and have not been reviewed by a lawyer.
- 25 questions: small-sample metrics, useful for regressions rather than absolute claims.
- LLM-judged metrics (RAGAS, citation correctness) depend on the judge model and can vary between runs.
- Latency is dominated by the Groq free tier (8K tokens/minute): concurrent requests queue or fail on rate limits.
- The latency benchmark runs first and alone, like the baseline; quality metrics run afterwards.
