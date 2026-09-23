import csv
import sys
from collections import Counter

import service
from db import SessionLocal
from models import Problem

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "Striver A2Z Tracker b9f4b27df1b34a8aa41ff0c3ed8155cd.csv"


def main() -> None:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    with SessionLocal() as session:
        existing = {
            p.problem_id
            for p in session.scalars(
                service.select(Problem).where(Problem.user_id == service.CURRENT_USER_ID)
            )
        }

        inserted = 0
        skipped = 0
        solved = 0
        diff_counts: Counter = Counter()

        for row in rows:
            problem_id = (row.get("Problem ID") or "").strip()
            if not problem_id or problem_id in existing:
                skipped += 1
                continue

            name = (row.get("Problem") or "").strip()
            desc = (row.get("Description") or "").strip()
            slug = (row.get("Link") or "").strip().rstrip("/").split("/")[-1]
            fallback = " ".join(w.capitalize() for w in slug.split("-"))
            description = f"{name}: {desc}" if desc else (name or fallback)

            topics = [t for t in (row.get("Topic"), row.get("Subtopic")) if t and t.strip()]
            is_solved = (row.get("Solved") or "").strip().lower() == "yes"
            mistakes = (row.get("Mistakes") or "").strip()
            difficulty = (row.get("Difficulty") or "medium").strip().lower()

            session.add(
                Problem(
                    user_id=service.CURRENT_USER_ID,
                    problem_id=problem_id,
                    problem_link=(row.get("Link") or "").strip(),
                    difficulty=difficulty,
                    problem_description=description,
                    topics=topics,
                    solved=is_solved,
                    mistakes=mistakes,
                    interval_days=0,
                    repetitions=0,
                    last_solved=None,
                )
            )
            inserted += 1
            diff_counts[difficulty] += 1
            if is_solved:
                solved += 1

        session.commit()

    print(f"inserted: {inserted} | skipped (duplicates): {skipped} | solved: {solved}")
    print(f"by difficulty: {dict(diff_counts)}")
    print(f"table now holds existing 2 + {inserted} imported = {inserted + 2} total")


if __name__ == "__main__":
    main()
