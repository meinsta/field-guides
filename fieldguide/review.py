"""review.py: an expert's comments become corrections, with no formatting asked of the expert.

A comment carries an anchor: the words the expert selected. The line holding those words is the
claim they objected to. That line is struck, recorded in Qdrant with the comment, and the next
build of any guide keeps the sentence out of "what ships today" until someone answers the comment.

    python3 -m fieldguide.review             # review.json against out/<id>.md, then rebuild
"""
import datetime, json, os

from fieldkit import qdrant as Q

from . import outline


def apply(spec="guide.json", comments="review.json", out="out"):
    g = json.load(open(spec))
    lines = open(os.path.join(out, g["id"] + ".md")).read().splitlines()
    cited = [m for l in lines if (m := outline.LINE.match(l)) and m["label"] == "Docs"]
    Q.hybrid_collection(outline.REVIEWS, keyword_indexes=("guide",))
    recorded, unplaced = [], []
    for c in json.load(open(comments)):
        hit = [m for m in cited if c["anchor"].lower() in m["text"].lower()]
        if len(hit) != 1:                          # no line, or more than one: a person places it, never a guess
            unplaced.append(c["anchor"])
            continue
        text = hit[0]["text"]
        Q.upsert(outline.REVIEWS, [Q.hybrid_point(Q.point_id(outline.REVIEWS, text), text, {
            "text": text, "guide": g["id"], "comment": c["comment"], "row": hit[0]["id"],
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()})])
        recorded.append(text)
    return recorded, unplaced


if __name__ == "__main__":
    recorded, unplaced = apply()
    print(f"struck {len(recorded)} line(s); could not place: {unplaced or 'none'}")
    path, n = outline.build()
    print(f"rebuilt {path}: {n} open item(s)")
