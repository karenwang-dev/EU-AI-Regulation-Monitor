import os

from dotenv import load_dotenv
from firecrawl import FirecrawlApp

load_dotenv()

app = FirecrawlApp(
    api_key=os.getenv("FIRECRAWL_API_KEY")
)


def crawl(url: str):

    result = app.scrape_url(
        url=url,
        formats=["markdown"]
    )

    return result