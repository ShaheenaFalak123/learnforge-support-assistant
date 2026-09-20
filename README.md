# LearnForge Support Assistant (Prototype)

A retrieval-augmented customer support assistant for LearnForge (a fictional
ed-tech company), built for the Applied AI/LLM Engineer take-home
assignment. It answers user questions from a small knowledge base (FAQs,
policy docs, past support tickets), handles multi-turn conversations, and
escalates to a human instead of guessing when it isn't confident.

See `DESIGN.md` for the architecture diagram and `SCHEMA.md` for the data
schema — this README covers the reasoning: failure handling, the eval
plan, and trade-offs.

## Setup & run (no external dependencies — standard library only)

1. Get a free Groq API key: https://console.groq.com/keys (no cost, no card required).
2. Set it as an environment variable:
   - Windows PowerShell: `$env:GROQ_API_KEY = "your-key-here"`
   - Mac/Linux: `export GROQ_API_KEY="your-key-here"`
3. Build the chunk index from the raw markdown (run once, or whenever `data/*.md` changes):
   ```
   python ingest.py
   ```
4. Run the assistant:
   ```
   python app.py
   ```
5. Optional — run the retrieval eval:
   ```
   python eval/run_eval.py
   ```

This project deliberately uses **zero third-party packages** (no
scikit-learn, no `requests`, no vector DB client) — everything is built on
`json`, `re`, `math`, `collections`, and `urllib` from the standard
library. See "Trade-offs" below for why, given the assignment's scale.

## Failure handling

- **Low-confidence / no relevant match** — before the LLM is even called, the retriever's top TF-IDF cosine score is checked against `CONFIDENCE_THRESHOLD` (0.12, chosen by eyeballing scores on `eval/eval_set.json`: real matches score ~0.35+, off-topic queries score ~0.10). Below that, the app escalates immediately without calling the LLM — this is the primary hallucination guard, and it's free (no API call).
- **Model answers anyway but is unsure** — even when retrieval finds something, the LLM itself may (correctly) not be confident. The system prompt instructs it to say so rather than guess, and `app.py` additionally scans the reply for uncertainty phrases ("not certain", "escalat...", etc.) as a cheap second signal, flagging the turn as escalated.
- **Stale or conflicting data** — the sample data intentionally contains outdated policy language next to explicit corrections (e.g. `POLICY-01` says annual subscriptions are "billed monthly" in an old sentence, then has an `IMPORTANT:` note correcting that). The system prompt tells the model to treat `IMPORTANT:`-prefixed text as an authoritative correction over older/conflicting text, and `ingest.py` flags any chunk containing one via `has_correction_note` so this could later be surfaced in a UI or weighted in ranking. Where two chunks conflict with **no** correction note (i.e. genuinely ambiguous, like the 7-day vs. 14-day refund policy), the model is instructed to say so explicitly rather than pick one arbitrarily — this mirrors how the real support agent handled it in `TICKET-08`, who escalated rather than guessed.
- **Bad/irrelevant retrieval** — if the top-k chunks are topically related but don't actually answer the question (e.g. a policy doc about the wrong product area), the system prompt's "don't guess" instruction is the backstop; the retrieval-confidence gate reduces how often this happens but doesn't eliminate it (see "Trade-offs").

## Eval plan

**Retrieval (automated, included):** `eval/eval_set.json` has 10 hand-labeled
queries across normal lookups, two intentional-contradiction cases,
one ambiguous ticket-style query, and two out-of-scope queries that
should escalate. `eval/run_eval.py` checks retrieval hit@3 against
expected chunk IDs, and for the escalation cases, checks that the top
score actually falls below the confidence threshold. This is cheap,
deterministic, and re-runs in under a second, so it's the kind of check
that belongs in CI.

**Answer quality / hallucination rate (manual/LLM-judge, not automated
here, but the design):** retrieval correctness doesn't guarantee the
generated answer is correct or non-hallucinated, so a real eval would add
a second pass over actual model outputs for the same eval set:

- **Groundedness check** — for each answer, verify every factual claim traces back to a cited chunk ID actually present in the retrieved context (either a human reviewer, or a second LLM call as a judge given the question, the answer, and the source chunks, asked to flag any unsupported claim).
- **Contradiction handling** — for `E3`/`E4` (the two contradiction cases), explicitly check the answer follows the corrected/current policy, not the outdated sentence next to it.
- **Escalation precision/recall** — of the cases that *should* escalate (`E6`, `E7`, plus any low-confidence real queries logged in production), what fraction actually did (recall), and of the cases the system escalated, how many were actually answerable (precision) — trading these off is a real product decision, not just a metric.
- **Hallucination rate** — % of answered (non-escalated) turns where the groundedness check fails. This is the single number I'd track over time as the corpus/prompt evolve.

In production, I'd also log every real user query + retrieved chunks +
answer + escalation flag, and periodically sample real traffic into the
eval set — synthetic eval sets like this one drift from what users
actually ask.

## Trade-offs (what I'd change with more time/budget, and why I chose X over Y)

- **TF-IDF over embeddings** — chosen because the corpus is tiny (40 chunks) and static for this exercise; TF-IDF needs no model download, no embedding API calls, and no vector DB, so the whole project runs instantly with zero installs. The real cost: TF-IDF only matches on shared vocabulary, so a paraphrase with no keyword overlap with the source text (e.g. "my card got dinged twice" instead of "duplicate payment") will retrieve worse than a semantic embedding model would. With more time/budget, I'd move to sentence embeddings (e.g. a small open model via a free-tier embeddings API, or a local model) plus a real vector DB (e.g. pgvector or a managed vector store) once the corpus is large enough or grows/updates frequently enough that in-memory TF-IDF stops being "instant."
- **No dependencies (stdlib-only) over convenience libraries** — chosen partly out of necessity (this dev machine's Python install turned out to have a corrupted stdlib file that broke `pip`, so this had to work either way), and partly because it makes the prototype trivially runnable by anyone with only Python installed — no install step, no dependency-version issues. Cost: I hand-rolled TF-IDF and an HTTP client instead of using battle-tested libraries (`scikit-learn`, `requests`), so there's more surface area for subtle bugs than a well-tested library would have.
- **Groq free-tier over other providers** — chosen for a genuinely free tier with no card requirement and fast inference, matching the assignment's "no cost, rate limits don't matter" constraint. Cost: `llama-3.1-8b-instant` is a small model; a larger/more capable free-tier model (or a paid one) would likely reduce hallucination and improve instruction-following further, which matters more once real users are involved.
- **Retrieval-confidence gating over always calling the LLM** — chosen because it's a free, deterministic hallucination guard (see "Failure handling"). Cost: a fixed cosine-similarity threshold is a blunt instrument — it doesn't adapt per query type, and it was tuned by eyeballing 10 examples rather than a proper calibration set. In production I'd calibrate this threshold against logged real traffic, and likely replace the flat threshold with something query-aware (e.g. also checking retrieval score *spread*, not just the top score, since a flat score distribution across top-k often means "nothing really matched").
- **Keyword-based uncertainty detection over a real confidence signal** — the post-generation escalation check (scanning for phrases like "not certain") is a cheap heuristic, not a real confidence measure, and both false-positives (a genuinely confident answer that happens to say "I'd note that...") and false-negatives (a wrong answer stated confidently) are possible. A production version would use either logprob-based confidence from the LLM API (when available) or a dedicated judge-model pass, at added latency/cost.
- **Single flat chunk per KB entry over finer-grained chunking** — chosen because every source entry here is already short (a few paragraphs); splitting further would add retrieval-index overhead without helping relevance at this size. This would need to change if entries grew much longer (e.g. full policy PDFs instead of short excerpts), where a single chunk could exceed useful context-window/relevance granularity.
- **No conversation persistence over stored session history** — chosen for a same-process CLI prototype where persistence wasn't required by the assignment. A real product needs sessions to survive process restarts and to support handoff to a human agent with full context, which would mean persisting `history` (and the escalation flag/reason) to a database keyed by session/user ID.

## Limitations of this prototype

- CLI only — no web UI, no auth, no persistence between runs.
- Confidence threshold and prompt were tuned against 10 hand-written eval queries, not real user traffic.
- No reranking step after retrieval — top-k is taken purely on TF-IDF score.
- No caching of repeated/similar queries.
