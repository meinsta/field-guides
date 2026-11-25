"""Offline checks against an in-memory stand-in for the cluster. Run: python3 test_offline.py"""
import json, os, re, tempfile

from fieldkit import qdrant as Q

from fieldguide import outline, review

words = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
STORE = {}
EU = "Route and driver data never leaves the region a workspace was created in."


def _fake():
    STORE.clear()
    def put(coll, source, text, **extra):
        pid = Q.point_id(coll, text)
        STORE.setdefault(coll, {})[pid] = {"id": pid, "payload": {"text": text, "source": source, **extra}}
    put(outline.COLL, "docs", EU)
    put(outline.COLL, "docs", "The old key keeps working for 24 hours.")
    put(outline.COLL, "field", "Legal needs confirmation that driver data stays inside the EU.", segment="enterprise", vertical="pharmacy logistics")
    Q.hybrid_collection = lambda name, **k: STORE.setdefault(name, {}) is None
    Q.hybrid_point = lambda pid, text, payload: {"id": pid, "payload": payload}
    Q.upsert = lambda name, pts, **k: STORE[name].update({p["id"]: p for p in pts})
    def query(name, q, limit=1, flt=None, **k):
        rows = [r for r in STORE.get(name, {}).values() if not flt or r["payload"]["source"] == flt["must"][0]["match"]["value"]]
        return sorted(rows, key=lambda r: -len(words(q) & words(r["payload"]["text"])))[:limit]
    Q.hybrid_query = query
    os.chdir(tempfile.mkdtemp())
    json.dump({"id": "g1", "title": "Guide one", "questions": [
        {"q": "Does driver data stay in the region?"}, {"q": "Does the old key keep working?"},
        {"q": "Can we bring our own keys?", "open": "No docs page yet."}]}, open("guide.json", "w"))


def test_outline_review_rebuild():
    _fake()
    path, n = outline.build()
    md = open(path).read()
    assert n == 1 and "Status: 1 open item(s)" in md and "Can we bring our own keys? Open: No docs page yet." in md
    part2 = md.split("## Part 2")[1].split("## Part 3")[0]
    assert EU in part2 and "24 hours" in part2 and "Customer (enterprise, pharmacy logistics)" in md.split("## Part 2")[0]

    json.dump([{"anchor": "never leaves the region", "comment": "Do backups stay in region too?"},
               {"anchor": "words that are in no line", "comment": "?"}], open("review.json", "w"))
    assert review.apply() == ([EU], ["words that are in no line"])
    path, n = outline.build()
    md = open(path).read()
    assert n == 2 and EU not in md.split("## Part 2")[1].split("## Part 3")[0]              # struck: out of what ships
    assert 'Struck in review of g1' in md and "Reviewer: Do backups stay in region too?" in md

    json.dump({"id": "g2", "title": "Guide two", "questions": [{"q": "Where does driver data live, by region?"}]}, open("guide.json", "w"))
    path, n = outline.build()
    assert n == 1 and "Struck in review of g1" in open(path).read()                         # the strike follows the sentence into another guide


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
