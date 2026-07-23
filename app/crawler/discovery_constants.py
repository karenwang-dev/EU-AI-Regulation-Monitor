"""Constants for Smart Discovery link crawling."""

SMART_DEFAULT_MAX_DEPTH = 2
SMART_DEFAULT_MAX_PAGES = 10
SINGLE_DEFAULT_MAX_DEPTH = 0
SINGLE_DEFAULT_MAX_PAGES = 1

MIN_SMART_MAX_DEPTH = 1
MIN_SMART_MAX_PAGES = 2

MAX_DISCOVERED_URLS = 200
MAX_LINKS_PER_PAGE = 100

DISCOVERY_FETCH_TIMEOUT_SECONDS = 30

TRACKING_QUERY_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
    }
)
