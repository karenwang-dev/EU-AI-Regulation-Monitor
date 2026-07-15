from app.crawler.crawler import crawl
from app.ai.analyzer import analyze_content
from app.storage.storage import save_result
from app.ai.content_cleaner import clean_content


def main():

    print("=" * 60)

    print("开始抓取法规网站...")

    result = crawl(
        "https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai"
    )

    print(
        "原始内容长度:",
        len(result.markdown)
    )


    print("开始清洗内容...")

    clean_markdown = clean_content(
        result.markdown
    )

    print(
        "清洗后长度:",
        len(clean_markdown)
    )


    print("开始AI分析...")

    analysis = analyze_content(
        clean_markdown
    )

    print("AI分析完成,开始保存...")


    print("保存结果...")

    save_result(
        analysis
    )

    print("完成!")

    print("=" * 60)


if __name__ == "__main__":
    main()