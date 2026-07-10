from pathlib import Path
from datetime import datetime
import json
import hashlib


RAW_DIR = Path("data/raw")
META_FILE = Path("data/metadata/snapshots.json")


def calculate_hash(content: str):

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()



def save_snapshot(
        source_id: str,
        content: str,
        url: str
):

    now = datetime.now()

    date_folder = now.strftime(
        "%Y-%m-%d"
    )

    timestamp = now.strftime(
        "%H%M%S"
    )


    folder = RAW_DIR / date_folder

    folder.mkdir(
        parents=True,
        exist_ok=True
    )


    filename = (
        f"{source_id}_{timestamp}.md"
    )


    file_path = folder / filename


    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(content)


    snapshot = {

        "source_id": source_id,

        "url": url,

        "timestamp":
            now.isoformat(),

        "file":
            str(file_path),

        "hash":
            calculate_hash(content)

    }


    save_metadata(snapshot)


    return file_path



def save_metadata(snapshot):

    META_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    if META_FILE.exists():

        with open(
            META_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

    else:

        data = []


    data.append(snapshot)


    with open(
        META_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )