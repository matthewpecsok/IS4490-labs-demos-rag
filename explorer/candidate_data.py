from pathlib import Path

MODULE3_DIR = Path(__file__).resolve().parent.parent / "module3"

CANDIDATES = {
    "elena-martinez": {
        "name": "Dr. Elena Martinez",
        "headline": "Chief Technology Officer, MedAxis Intelligence",
        "location": "Salt Lake City, UT",
        "file": "resume_1_elena_martinez.md",
    },
    "marcus-reed": {
        "name": "Marcus Reed",
        "headline": "Engineering Manager, growth-stage SaaS",
        "location": "Boise, ID",
        "file": "resume_2_marcus_reed.md",
    },
    "olivia-grant": {
        "name": "Olivia Grant",
        "headline": "Senior Events Manager, hospitality",
        "location": "Park City, UT",
        "file": "resume_3_olivia_grant.md",
    },
}


def _read(filename):
    return (MODULE3_DIR / filename).read_text(encoding="utf-8").strip()


CANDIDATE_DOCUMENTS = {
    candidate_id: {
        "title": candidate["name"],
        "candidate_name": candidate["name"],
        "headline": candidate["headline"],
        "location": candidate["location"],
        "content": _read(candidate["file"]),
    }
    for candidate_id, candidate in CANDIDATES.items()
}

JOB_POSTING_TITLE = "Chief Technology Officer — BrightPath Health Analytics"
JOB_POSTING_TEXT = _read("cto_job_posting.md")
