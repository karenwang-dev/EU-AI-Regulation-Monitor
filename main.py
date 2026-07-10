from app.analyzer import analyze_content
from app.storage import save_result


def main():

    test_content = """

    European Commission published new requirements
    for connected devices and smart televisions.

    """

    result = analyze_content(
        test_content
    )

    file = save_result(result)

    print()

    print("保存成功：")

    print(file)


if __name__ == "__main__":
    main()