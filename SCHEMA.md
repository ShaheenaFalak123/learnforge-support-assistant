# Data Schema

## Source data (given)

Three markdown files under `data/`, each a sequence of entries separated by
a `---` line: `faqs.md` (15 entries), `policies.md` (10 entries), and
`tickets.md` (15 entries). `ingest.py` parses these into a single flat list
of **chunk** records, one per entry, written to `data/chunks.json`.

## Chunk record (the unit the retriever indexes and the LLM cites)

```json
{
  "id": "POLICY-01",
  "source": "policies.md",
  "type": "policy",
  "title": "Subscription Plans and Billing",
  "text": "LearnForge subscriptions provide access to ... Last reviewed: February 2026.",
  "last_reviewed": "February 2026",
  "status": null,
  "has_correction_note": true
}
```

| Field               | Type          | Meaning                                                                                          |
| ------------------- | ------------- | -------------------------------------------------------------------------------------------------|
| `id`                | string        | Stable ID from the source heading (e.g. `FAQ-03`, `POLICY-01`, `TICKET-08`). Used for citations.  |
| `source`            | string        | Originating file (`faqs.md` / `policies.md` / `tickets.md`).                                      |
| `type`              | enum          | `"faq"` \| `"policy"` \| `"ticket"` — lets the prompt/UI weight or label sources differently.      |
| `title`             | string        | Short human-readable heading, shown to the user alongside citations.                              |
| `text`              | string        | Full entry body (question+answer, policy text, or full ticket transcript) — this is what's embedded/indexed and what's inserted into the LLM's context. |
| `last_reviewed`     | string \| null| Extracted "Last reviewed:" / "Updated:" date if the source stated one — used for staleness signals.|
| `status`            | string \| null| For tickets only: the `STATUS:` line (e.g. `Resolved`, `Escalated`).                              |
| `has_correction_note` | boolean     | True if the entry contains an explicit `IMPORTANT:` correction — a hint that this chunk supersedes older/conflicting info elsewhere in the corpus. |

One chunk = one source entry (not further split into smaller passages). At
this corpus size (40 entries, all short), splitting further would only add
retrieval overhead without a quality benefit — see README "Trade-offs" for
when that changes.

## Retrieval index (in-memory, not persisted)

`retriever.py` builds a TF-IDF vector per chunk **in memory at startup**
from `chunks.json` — there's no separate vector DB file or embedding
store in this prototype. Conceptually, each indexed record is:

```json
{
  "chunk_id": "POLICY-01",
  "vector": { "subscription": 0.41, "annual": 0.37, "billing": 0.29, "...": "..." }
}
```

i.e. a sparse `{term: tf-idf weight}` map, plus the precomputed vector norm
used for cosine similarity. In a production version, this record shape
maps directly onto a vector DB row: `{id, embedding (dense vector instead
of sparse TF-IDF), metadata: {source, type, title, last_reviewed, status}}`
— see README "Trade-offs" for why TF-IDF was chosen over embeddings here.

## Conversation state (per session, in-memory)

```json
{"role": "user" | "assistant", "content": "..."}
```

A simple list, appended each turn and passed back to the LLM (last N turns)
for multi-turn context. Not persisted between runs in this prototype — see
README "What I'd change with more time" for session persistence.
