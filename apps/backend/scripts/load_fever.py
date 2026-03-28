"""Script to load and inspect FEVER data."""

from app.services.benchmark.fever_loader import load_fever_claims

if __name__ == "__main__":
    claims = load_fever_claims("data/fever/dev.jsonl", limit=10)
    for c in claims:
        print(f"[{c['label']}] {c['claim'][:80]}")
    print(f"\nTotal loaded: {len(claims)}")
