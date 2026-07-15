from firecrawl import FirecrawlApp

from app.core.config import FIRECRAWL_API_KEY


app = FirecrawlApp(
    api_key=FIRECRAWL_API_KEY
)


def crawl_url(url: str):

    result = app.scrape(
        url,
        formats=[
            "markdown"
        ]
    )

    return result