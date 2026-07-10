from app.source_loader import load_sources
from app.firecrawl_service import crawl_url
from app.raw_storage import save_raw_content


def main():

    sources = load_sources()


    for source in sources:

        if not source["enabled"]:
            continue


        print()
        print("=" * 50)

        print(
            f"开始抓取: {source['name']}"
        )


        try:

            result = crawl_url(
                source["url"]
            )


            file = save_raw_content(
                source["id"],
                result.markdown
            )


            print(
                "保存成功:"
            )

            print(file)


        except Exception as e:

            print(
                "抓取失败:"
            )

            print(e)



if __name__ == "__main__":
    main()