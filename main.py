from app.source_loader import load_sources
from app.firecrawl_service import crawl_url
from app.raw_storage import save_raw_content


def main():

    sources = load_sources()


    first_source = sources[0]


    print(
        "开始抓取:"
    )

    print(
        first_source["name"]
    )


    result = crawl_url(
        first_source["url"]
    )


    file = save_raw_content(
        first_source["id"],
        result.markdown
    )


    print()

    print(
        "保存成功:"
    )

    print(file)



if __name__ == "__main__":
    main()