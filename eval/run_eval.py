"""
Automated part of the eval plan: retrieval quality.

For each labeled query in eval_set.json, checks whether any of the
"expected_chunk_ids" appear in the top-k retrieved chunks (hit@k). For the
two "escalation" cases, expected_chunk_ids is empty on purpose — success
there means the top score falls below CONFIDENCE_THRESHOLD, so the app
escalates instead of answering from irrelevant context.

This only scores retrieval, not generation quality/hallucination — see
README "Eval plan" for how the generation side (answer correctness,
hallucination rate, contradiction handling) is measured, which needs a
human or LLM-judge pass over actual model outputs, not just retrieval.

Run: python eval/run_eval.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from retriever import Retriever  # noqa: E402
from app import CONFIDENCE_THRESHOLD  # noqa: E402

EVAL_PATH = Path(__file__).parent / "eval_set.json"


def main():
    retriever = Retriever()
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))

    passed = 0
    for case in cases:
        results = retriever.search(case["query"], top_k=3)
        retrieved_ids = [r["chunk"]["id"] for r in results]
        top_score = results[0]["score"] if results else 0.0

        if case["category"] == "escalation":
            ok = top_score < CONFIDENCE_THRESHOLD
            detail = f"top_score={top_score:.3f} (threshold={CONFIDENCE_THRESHOLD})"
        else:
            ok = any(cid in retrieved_ids for cid in case["expected_chunk_ids"])
            detail = f"expected one of {case['expected_chunk_ids']}, got {retrieved_ids}"

        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['id']} ({case['category']}): {case['query']}")
        print(f"        {detail}")

    print(f"\n{passed}/{len(cases)} retrieval cases passed.")


if __name__ == "__main__":
    main()
