"""
Parses the raw markdown knowledge base (data/faqs.md, policies.md, tickets.md)
into a flat list of chunk records and writes them to data/chunks.json.

Run this once (and again any time the source .md files change) before
starting app.py.
"""
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
HEADING_RE = re.compile(r"^#\s*([A-Za-z]+-\d+)\s*[—-]\s*(.+)$", re.MULTILINE)
LAST_REVIEWED_RE = re.compile(r"Last reviewed:\s*(.+)", re.IGNORECASE)
STATUS_RE = re.compile(r"STATUS:\s*(.+)", re.IGNORECASE)

SOURCES = [
    ("faqs.md", "faq"),
    ("policies.md", "policy"),
    ("tickets.md", "ticket"),
]


def split_entries(raw_text: str):
    """Each entry in these files is separated by a line containing only '---'."""
    blocks = re.split(r"\n\s*-{3,}\s*\n", raw_text)
    return [b.strip() for b in blocks if b.strip()]


def parse_file(filename: str, doc_type: str):
    path = DATA_DIR / filename
    raw = path.read_text(encoding="utf-8")
    chunks = []
    for block in split_entries(raw):
        m = HEADING_RE.search(block)
        if not m:
            continue  # skip the top-of-file title block, e.g. "# LearnForge FAQs"
        chunk_id, title = m.group(1), m.group(2).strip()
        body = block[m.end():].strip()

        last_reviewed = None
        m2 = LAST_REVIEWED_RE.search(body)
        if m2:
            last_reviewed = m2.group(1).strip().rstrip(".")

        status = None
        m3 = STATUS_RE.search(body)
        if m3:
            status = m3.group(1).strip().rstrip(".")

        chunks.append(
            {
                "id": chunk_id,
                "source": filename,
                "type": doc_type,
                "title": title,
                "text": body,
                "last_reviewed": last_reviewed,
                "status": status,
                "has_correction_note": "IMPORTANT" in body,
            }
        )
    return chunks


def main():
    all_chunks = []
    for filename, doc_type in SOURCES:
        file_chunks = parse_file(filename, doc_type)
        print(f"{filename}: parsed {len(file_chunks)} chunks")
        all_chunks.extend(file_chunks)

    out_path = DATA_DIR / "chunks.json"
    out_path.write_text(json.dumps(all_chunks, indent=2), encoding="utf-8")
    print(f"\nWrote {len(all_chunks)} total chunks to {out_path}")


if __name__ == "__main__":
    main()
