REMOVE_PATTERNS = [
    "Accept all cookies",
    "Accept only essential cookies",
    "Follow us",
    "Jobs",
    "Funding and tenders",
    "Visit the European Commission",
    "Search on:",
    "Language",
    "Cookies"
]


def clean_content(markdown: str) -> str:

    text = markdown

    print(f"Before Cleaning: {len(markdown)} chars")

    for item in REMOVE_PATTERNS:
        text = text.replace(item, "")

    print(f"After Cleaning : {len(text)} chars")

    return text