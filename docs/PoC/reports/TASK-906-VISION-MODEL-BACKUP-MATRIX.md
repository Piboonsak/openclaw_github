# TASK-906 Vision Model Backup Matrix

Sample: Comp_3, 10 PDFs, seed 910, max 4 pages, max file 25MB.

| Rank | Model | Result | Rows | Green/Amber/Red | Stock candidates | Cost THB | Avg sec/doc | Notes |
|---:|---|---|---:|---|---:|---:|---:|---|
| 1 | `google/gemini-2.5-flash-lite` | PASS | 28 | 4/24/0 | 24 | 0.1525 | 5.10 | OK |
| 2 | `openai/gpt-4.1-nano` | PASS | 28 | 4/24/0 | 24 | 0.2503 | 4.66 | OK |
| 3 | `google/gemini-3.1-flash-lite` | PASS | 28 | 4/24/0 | 24 | 1.8818 | 3.32 | OK |
| 4 | `openai/gpt-4o-mini` | PASS | 28 | 4/24/0 | 24 | 13.4590 | 6.48 | OK |
| 5 | `qwen/qwen3-vl-8b-instruct` | FAIL 10/10 | 0 | 0/0/0 | 0 | 0.0000 | 0.53 | NotFoundError: Error code: 404 - {'error': {'message': 'No allowed providers are available for the selected model.', 'co |
| 6 | `mistralai/mistral-small-3.2-24b-instruct` | FAIL 10/10 | 0 | 0/0/0 | 0 | 0.0000 | 0.55 | NotFoundError: Error code: 404 - {'error': {'message': 'No allowed providers are available for the selected model.', 'co |
| 7 | `qwen/qwen3-vl-32b-instruct` | FAIL 10/10 | 0 | 0/0/0 | 0 | 0.0000 | 0.60 | NotFoundError: Error code: 404 - {'error': {'message': 'No allowed providers are available for the selected model.', 'co |

## Recommendation
Primary stays `google/gemini-2.5-flash-lite`. First non-Gemini backup is `openai/gpt-4.1-nano` because it passed with identical row counts and low cost. Keep `google/gemini-3.1-flash-lite` as same-family fallback if 2.5 is unavailable, but watch cost. `openai/gpt-4o-mini` works but is too expensive for normal fallback. Qwen/Mistral candidates failed this OpenRouter PDF/image pipeline smoke test and need a separate image-render adapter before they can be considered production backups.