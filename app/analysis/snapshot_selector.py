import json
from pathlib import Path


META_FILE = Path(
    "data/metadata/snapshots.json"
)


def get_latest_snapshots(source_id: str):

    with open(
        META_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        snapshots = json.load(f)


    filtered = [
        item
        for item in snapshots
        if item["source_id"] == source_id
    ]


    filtered.sort(
        key=lambda x:x["timestamp"]
    )


    if len(filtered) < 2:
        return None


    return (
        filtered[-2],
        filtered[-1]
    )