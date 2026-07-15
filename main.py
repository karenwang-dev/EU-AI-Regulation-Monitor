import sys

from app.pipeline import run_pipeline


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "run":
        print("Usage: python main.py run")
        sys.exit(1)

    print("=" * 60)
    print("AI Regulation Monitoring Pipeline")
    print("=" * 60)

    results = run_pipeline()

    print("\n" + "=" * 60)
    print("Pipeline Summary")
    print("=" * 60)

    for result in results:
        print(
            f"- {result['name']}: {result['status']} "
            f"(snapshot={result['snapshot_id']}, "
            f"diff={result.get('diff_id')})"
        )

    print("=" * 60)


if __name__ == "__main__":
    main()
