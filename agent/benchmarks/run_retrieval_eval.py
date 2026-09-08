"""
Runbook retrieval benchmark — precision@1 over a labelled query set.

Run:
    cd agent
    .venv/Scripts/python.exe benchmarks/run_retrieval_eval.py

Scores the RunbookAgent's top-1 result against a human label for each query in
`runbook_queries.json`. Prints per-query results and a headline number.

Read the number honestly. The corpus is three runbooks, so the random-guess
floor is ~33% and a perfect score would be more suspicious than a good one —
four of the twelve queries are deliberately ambiguous. The point of the set is
to make the claim reproducible and to show *which* cases fail, not to produce a
flattering figure.

Exit code is 0 regardless of score: this is a measurement, not a pass/fail gate.
`tests/test_retrieval_benchmark.py` holds the regression assertion.
"""

import asyncio
import json
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

from app.core.agents.runbook_agent import RunbookAgent  # noqa: E402
from app.db.load_runbooks import load_runbooks  # noqa: E402

QUERIES = Path(__file__).parent / "runbook_queries.json"


def normalise(title: str) -> str:
    """Map a retrieved runbook title back to its corpus id.

    ChromaStore returns the document title ("Api Timeout"), while the labels use
    the filename stem ("api_timeout"). Comparing those directly would score
    every query as a miss.
    """
    return title.strip().lower().replace(" ", "_").replace("-", "_")


async def main() -> int:
    spec = json.loads(QUERIES.read_text(encoding="utf-8"))
    queries = spec["queries"]

    # Index first: the vector store is rebuilt at startup in production, so an
    # unseeded run here would measure an empty corpus.
    indexed = load_runbooks()
    print(f"Indexed {indexed} runbooks into the vector store\n")

    agent = RunbookAgent()
    hits, misses = 0, []

    for q in queries:
        results = await agent.search([q["query"]])
        top = normalise(results[0]["title"]) if results else "<no result>"
        expected = q["expected"]
        ok = top == expected

        if ok:
            hits += 1
        else:
            misses.append((q, top))

        flag = "hard" if q.get("hard") else "    "
        print(f"  {'PASS' if ok else 'FAIL'}  {q['id']}  [{flag}]  "
              f"expected={expected:<13} got={top}")

    total = len(queries)
    pct = 100.0 * hits / total
    hard_total = sum(1 for q in queries if q.get("hard"))
    hard_hits = sum(1 for q in queries if q.get("hard")
                    and q["id"] not in {m[0]["id"] for m in misses})

    print(f"\nprecision@1: {hits}/{total} ({pct:.0f}%)")
    print(f"  on the {hard_total} ambiguous queries: {hard_hits}/{hard_total}")
    print(f"  on the {total - hard_total} clear-cut queries: "
          f"{hits - hard_hits}/{total - hard_total}")
    print(f"  random-guess floor for a {len(spec['corpus'])}-runbook corpus: "
          f"~{100 / len(spec['corpus']):.0f}%")

    if misses:
        print("\nMisses:")
        for q, got in misses:
            print(f"  {q['id']}  \"{q['query']}\"")
            print(f"        expected {q['expected']}, retrieved {got}")
            if q.get("ambiguity_note"):
                print(f"        note: {q['ambiguity_note']}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
