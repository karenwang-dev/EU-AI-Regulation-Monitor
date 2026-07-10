from app.source_loader import load_sources


def main():

    sources = load_sources()

    print("=" * 50)

    print("Monitoring Sources")

    print("=" * 50)

    for source in sources:

        print(f"{source['name']}")

        print(source["url"])

        print()


if __name__ == "__main__":
    main()