"""CSV import: parse an arbitrary problems CSV into Revizo rows.

The uploader's CSV can have any columns in any order with any extra data —
we only look for the fields Revizo tracks (see `FIELD_SYNONYMS`). A row is
importable only if it has both a title and a link; anything else is skipped
and reported back to the user so they can fix their file.
"""

import csv
import io
from dataclasses import dataclass, field

MAX_FILE_BYTES = 1_000_000  # 1 MB
MAX_ROWS = 5000

DIFFICULTY_ALIASES = {
    "easy": "easy",
    "medium": "medium",
    "med": "medium",
    "hard": "hard",
    "": "medium",
}

# canonical field -> header names we accept (compared lowercase/stripped)
FIELD_SYNONYMS = {
    "title": ("problem", "title", "problem name", "problem title", "name"),
    "link": ("link", "problem link", "url", "problem url"),
    "difficulty": ("difficulty", "level"),
    "topics": ("topics", "topic", "subtopic", "tags", "tag"),
    "description": ("description", "problem statement", "notes", "approach"),
}


@dataclass
class Skip:
    row_number: int  # 1-based data row number (excluding the header)
    reason: str


@dataclass
class ParsedCsv:
    rows: list[dict] = field(default_factory=list)  # canonical-field dicts
    skipped: list[Skip] = field(default_factory=list)
    extras_ignored: list[str] = field(default_factory=list)  # unmatched headers
    too_many_rows: bool = False


def _matched_field(header: str) -> str | None:
    h = header.strip().lower()
    for canonical, names in FIELD_SYNONYMS.items():
        if h in names:
            return canonical
    return None


def _split_topics(raw: str) -> list[str]:
    return [t.strip() for t in raw.replace(";", ",").split(",") if t.strip()]


def _normalize_difficulty(raw: str) -> str:
    return DIFFICULTY_ALIASES.get(raw.strip().lower(), "medium")


def parse_csv(text: str) -> ParsedCsv:
    """Parse CSV text into canonical rows; skip rows missing title or link.

    Raises ValueError with a user-facing message for structurally broken
    input (no usable header, or completely empty).
    """
    result = ParsedCsv()
    try:
        reader = csv.reader(io.StringIO(text))
        header = next(reader)
    except StopIteration:
        raise ValueError("The file looks empty — upload a CSV with a header row and problems.")

    # Column index -> canonical field
    mapping: dict[int, str] = {}
    for i, name in enumerate(header):
        canonical = _matched_field(name)
        if canonical and canonical not in mapping.values():
            mapping[i] = canonical
        elif not canonical:
            result.extras_ignored.append(name.strip())

    if not any(f in mapping.values() for f in ("title", "link")):
        raise ValueError(
            "Couldn't find the required columns. The CSV needs at least a "
            "problem/title column and a link/url column — see /docs/importing."
        )

    for row_number, raw_row in enumerate(reader, start=1):
        if not raw_row or not any(cell.strip() for cell in raw_row):
            continue  # blank line
        if len(result.rows) + len(result.skipped) >= MAX_ROWS:
            result.too_many_rows = True
            break

        # honor quoted multi-line cells: map only the fields we know about
        values: dict[str, str] = {}
        for idx, canonical in mapping.items():
            if idx < len(raw_row):
                values[canonical] = raw_row[idx].strip()

        title, link = values.get("title", ""), values.get("link", "")
        if not title and not link:
            continue  # fully empty data row, not worth reporting
        if not title:
            result.skipped.append(Skip(row_number, "missing title"))
            continue
        if not link:
            result.skipped.append(Skip(row_number, "missing link"))
            continue

        result.rows.append(
            {
                "title": title,
                "link": link,
                "difficulty": _normalize_difficulty(values.get("difficulty", "medium")),
                "topics": _split_topics(values.get("topics", "")),
                "description": values.get("description", ""),
            }
        )
    return result
