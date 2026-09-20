"""
LearnForge Support Assistant — CLI prototype.

Flow per turn:
  1. Retrieve top-k relevant chunks for the user's question (TF-IDF).
  2. If the best match score is below CONFIDENCE_THRESHOLD, skip the LLM
     entirely and escalate to a human (cheap, and avoids the model
     inventing an answer from irrelevant context).
  3. Otherwise, build a prompt containing: a system instruction, the
     retrieved chunks (with IDs so the model can cite them), and recent
     conversation history (for multi-turn), then call the LLM.
  4. Scan the LLM's own reply for uncertainty language as a second,
     cheap escalation signal.

Run:  python app.py   (after running ingest.py once)
"""
from retriever import Retriever
from llm_client import chat_completion

CONFIDENCE_THRESHOLD = 0.12  # tuned by eyeballing scores on eval/eval_set.json — see README
MAX_HISTORY_TURNS = 4  # how many prior user/assistant turns to keep for context

SYSTEM_PROMPT = """You are the LearnForge customer support assistant.

Rules:
- Answer ONLY using the information in the "Context" section below. Do not use outside knowledge.
- Every context chunk has an ID like [FAQ-03] or [POLICY-02] or [TICKET-11]. Cite the chunk ID(s) you relied on in square brackets at the end of relevant sentences.
- Some context may be outdated or contradictory. If a chunk contains a line starting with "IMPORTANT:", that is a correction — prefer it over older/conflicting text in the same or other chunks. If chunks genuinely conflict with no correction note, say so explicitly instead of picking one arbitrarily.
- If the context does not clearly answer the question, do NOT guess. Say you're not certain and that you're escalating to a human support agent.
- Keep answers concise and friendly, like a real support agent.
"""

ESCALATION_PHRASES = [
    "escalat",
    "not certain",
    "not confident",
    "human support agent",
    "i don't have enough information",
    "i'm not sure",
]


def build_context_block(results):
    lines = []
    for r in results:
        c = r["chunk"]
        lines.append(f"[{c['id']}] ({c['type']}, score={r['score']:.2f}) {c['title']}\n{c['text']}")
    return "\n\n---\n\n".join(lines)


def looks_like_escalation(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in ESCALATION_PHRASES)


def main():
    retriever = Retriever()
    history = []  # list of {"role": "user"/"assistant", "content": str}

    print("LearnForge Support Assistant (prototype). Type 'exit' to quit.\n")
    while True:
        query = input("You: ").strip()
        if not query:
            continue
        if query.lower() in {"exit", "quit"}:
            break

        results = retriever.search(query, top_k=3)
        top_score = results[0]["score"] if results else 0.0

        if top_score < CONFIDENCE_THRESHOLD:
            answer = (
                "I'm not confident I have accurate information on that in our "
                "knowledge base. Let me connect you with a human support agent "
                "who can help further. [ESCALATED: low retrieval confidence]"
            )
            print(f"Assistant: {answer}\n")
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": answer})
            continue

        context_block = build_context_block(results)
        messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\nContext:\n" + context_block}]
        messages.extend(history[-2 * MAX_HISTORY_TURNS :])
        messages.append({"role": "user", "content": query})

        answer = chat_completion(messages)
        if looks_like_escalation(answer):
            answer += "\n[ESCALATED: model expressed low confidence]"

        print(f"Assistant: {answer}\n")
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
