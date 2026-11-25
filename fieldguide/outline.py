"""outline.py: a deal-backed guide outline in three parts, built from the grounded collection.

  Part 1  who is asking: field notes, by segment and vertical
  Part 2  what ships today: one docs line per question, each with the id of its row
  Part 3  open before publishing: questions the docs do not answer yet, and every line an expert struck

Nothing reaches Part 2 without a row behind it, and a line an expert struck in any guide stays out
of Part 2 in every guide. The outline is internal until Part 3 is empty.

    python3 -m fieldguide.outline            # guide.json -> out/<id>.md
"""
import json, os, re

from fieldkit import approvals, qdrant as Q

COLL = os.environ.get("FIELD_COLLECTION", "grounding")
REVIEWS = os.environ.get("GUIDE_REVIEWS", "guide_reviews")
LINE = re.compile(r"^- (?P<label>[^:]+): (?P<text>.*) `\[(?P<id>[0-9a-f-]{36})\]`$")


def _lane(source):
    return {"must": [{"key": "source", "match": {"value": source}}]}


def line(row):
    p = row["payload"]
    label = "Docs" if p["source"] == "docs" else f"Customer ({p['segment']}, {p['vertical']})"
    return f"- {label}: {p['text']} `[{row['id']}]`"


def struck(text):
    """The review that struck this exact sentence, in any guide, or None. Raises when the review
    memory is unreachable: a build that cannot read its reviews must not ship struck lines."""
    Q.hybrid_collection(REVIEWS, keyword_indexes=("guide",))
    for p in Q.hybrid_query(REVIEWS, text, limit=3):
        if approvals.norm(p["payload"]["text"]) == approvals.norm(text):
            return p["payload"]
    return None


def build(spec="guide.json", out="out"):
    g = json.load(open(spec))
    asking, ships, open_items = [], [], []
    for item in g["questions"]:
        q = item["q"]
        asking += [f"### {q}"] + [line(r) for r in Q.hybrid_query(COLL, q, limit=1, flt=_lane("field"))] + [""]
        if item.get("open"):
            open_items.append(f"- {q} Open: {item['open']}")
            continue
        docs = Q.hybrid_query(COLL, q, limit=1, flt=_lane("docs"))
        review = struck(docs[0]["payload"]["text"]) if docs else None
        if not docs:
            open_items.append(f"- {q} Open: no docs line answers this.")
        elif review:
            open_items.append(f"- {q} Struck in review of {review['guide']}: \"{docs[0]['payload']['text']}\" Reviewer: {review['comment']}")
        else:
            ships += [f"### {q}", line(docs[0]), ""]
    status = f"Status: {len(open_items)} open item(s). Internal until this reads 0." if open_items else "Status: 0 open items. Ready to draft."
    md = [f"# {g['title']}", "", status, "", "## Part 1: Who is asking", ""] + asking \
        + ["## Part 2: What ships today", ""] + ships + ["## Part 3: Open before publishing", ""] + open_items + [""]
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, g["id"] + ".md")
    open(path, "w").write("\n".join(md))
    return path, len(open_items)


if __name__ == "__main__":
    path, n = build()
    print(f"built {path}: {n} open item(s)")
