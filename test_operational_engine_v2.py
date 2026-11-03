import hashlib
import json
import re
import sys
from pathlib import Path

from operational_query_engine import answer_operational_question

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "benchmark_frozen_v2.txt"

FROZEN_HASHES_REQUIRED = {
    "operations_v2.db":
        "06e10a9dbd17eb47a9ed960296b62f164f38fb65aee9e6d1bdf2741e854729f3",
    "eval_questions_v2.json":
        "c3da6b2b8c08c64dc6052cef714795412386ebeeaa6e6e2657f135a5586bc5b4",
    "eval_heldout_v1.json":
        "bb71bf4a424bfdf83cc24a47093a3fc7b7aacdda90b2d836d7822154cdca5269",
}

EXPECTED_STATUSES = {
    **{f"A{i}": "answered" for i in range(1, 11)},
    "B1": "clarification_required",
    "B2": "answered",
    "B3": "clarification_required",
    **{f"U{i}": "refused" for i in range(1, 5)},
    **{f"N{i}": "unanswerable" for i in range(1, 4)},
}

EXPECTED_RESULTS = {
    "A1": [["auth-api", 2], ["orders-api", 1], ["payments-api", 6]],
    "A2": [["auth-api", 2], ["orders-api", 1], ["payments-api", 6]],
    "A3": [["auth-api", 2], ["orders-api", 1], ["payments-api", 6]],
    "A4": {
        "count": 3,
        "incidents": [
            ["INC-100", "2026-10-12T10:10:00Z"],
            ["INC-101", "2026-10-11T14:15:00Z"],
            ["INC-102", "2026-10-11T12:00:00Z"],
        ],
    },
    "A5": [
        ["INC-100", "2026-10-12T10:10:00Z"],
        ["INC-101", "2026-10-11T14:15:00Z"],
        ["INC-102", "2026-10-11T12:00:00Z"],
    ],
    "A6": {
        "deployment_id": "DEP-001",
        "before_error_count": 2,
        "after_error_count": 4,
        "before_window": ["2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z"],
        "after_window": ["2026-10-12T10:00:00Z", "2026-10-12T11:00:00Z"],
        "difference_after_minus_before": 2,
        "required_interpretation": (
            "2 more recorded errors observed after the deployment; "
            "this does not establish causation."
        ),
    },
    "A7": {
        "deployment_id": "DEP-001",
        "before_error_count": 2,
        "after_error_count": 4,
        "before_window": ["2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z"],
        "after_window": ["2026-10-12T10:00:00Z", "2026-10-12T11:00:00Z"],
        "difference_after_minus_before": 2,
        "required_interpretation": (
            "2 more recorded errors observed after the deployment; "
            "this does not establish causation."
        ),
    },
    "A8": {
        "deployment_id": "DEP-002",
        "before_error_count": 0,
        "after_error_count": 1,
        "before_window": ["2026-10-11T13:00:00Z", "2026-10-11T14:00:00Z"],
        "after_window": ["2026-10-11T14:00:00Z", "2026-10-11T15:00:00Z"],
        "required_wording": "1 recorded error observed after, 0 before.",
    },
    "A9": {
        "deployment_id": "DEP-002",
        "before_error_count": 0,
        "after_error_count": 1,
        "before_window": ["2026-10-11T13:00:00Z", "2026-10-11T14:00:00Z"],
        "after_window": ["2026-10-11T14:00:00Z", "2026-10-11T15:00:00Z"],
        "required_wording": "1 recorded error observed after, 0 before.",
    },
    "A10": [
        [
            "DEP-003", "SVC-003", "auth-api", "staging",
            "2026-10-12T09:30:00Z", "failed"
        ]
    ],
    "B2": 4,
}

PARAPHRASES = [
    (
        "Count errors for each service during the last 24 hours.",
        "A1",
    ),
    (
        "Give me per-service error totals for the past 24 hours.",
        "A2",
    ),
    (
        "Compare error counts in the hour before and after DEP-001.",
        "A6",
    ),
    (
        "How many errors occurred in the hour before and the hour "
        "after deployment DEP-002?",
        "A8",
    ),
    (
        "List deployments with a failed status.",
        "A10",
    ),
]


def check(label, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"{status}: {label}{suffix}")
    return bool(passed)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest_hashes():
    """Read lines formatted as filename : 64-character SHA-256."""
    hashes = {}

    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(
            f"Missing hash manifest: {MANIFEST_PATH.name}"
        )

    for line in MANIFEST_PATH.read_text(
        encoding="utf-8-sig"
    ).splitlines():
        match = re.match(
            r"^\s*(.+?)\s*:\s*([0-9a-fA-F]{64})\s*$",
            line,
        )
        if match:
            filename, digest = match.groups()
            hashes[Path(filename.strip()).name] = digest.lower()

    return hashes


def normalize_unordered_rows(value):
    """
    Ignore row order for lists of rows.
    Preserve column order, dictionary values, and ordinary list order
    (including before/after time windows).
    """
    if isinstance(value, dict):
        return {
            key: normalize_unordered_rows(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        if value and all(isinstance(row, list) for row in value):
            normalized_rows = [
                tuple(normalize_unordered_rows(cell) for cell in row)
                for row in value
            ]
            return ("unordered_rows", tuple(sorted(normalized_rows, key=repr)))

        return [normalize_unordered_rows(item) for item in value]

    return value


def results_equal(actual, expected):
    return normalize_unordered_rows(actual) == normalize_unordered_rows(expected)


def main():
    failures = 0
    checks = 0

    def record(label, passed, detail=""):
        nonlocal failures, checks
        checks += 1
        if not check(label, passed, detail):
            failures += 1

    print("=== 1. Frozen manifest and file integrity ===")

    try:
        manifest_hashes = read_manifest_hashes()
        record("Manifest can be parsed", True)

        # Verify the three originally frozen artifacts against both
        # the manifest and the known hashes supplied for this benchmark.
        for filename, known_hash in FROZEN_HASHES_REQUIRED.items():
            path = ROOT / filename
            manifest_hash = manifest_hashes.get(filename)

            if not path.is_file():
                record(f"Hash integrity: {filename}", False, "file missing")
                continue

            actual_hash = sha256(path)
            passed = (
                manifest_hash is not None
                and manifest_hash == known_hash
                and actual_hash == manifest_hash
            )
            detail = "matches manifest and frozen reference" if passed else (
                "manifest entry, file hash, or frozen reference differs"
            )
            record(f"Hash integrity: {filename}", passed, detail)

        # Any additional hash entries are also checked automatically.
        # This allows script hashes to be added after those scripts
        # have been finalized.
        for filename, expected_hash in sorted(manifest_hashes.items()):
            if filename in FROZEN_HASHES_REQUIRED:
                continue

            path = ROOT / filename
            if not path.is_file():
                record(f"Manifest-listed file: {filename}", False, "file missing")
            else:
                record(
                    f"Manifest hash: {filename}",
                    sha256(path) == expected_hash,
                    "matches manifest" if sha256(path) == expected_hash
                    else "SHA-256 mismatch",
                )

    except Exception as exc:
        record("Manifest verification", False, str(exc))
        print("\nCannot continue reliably without the frozen manifest.")
        raise SystemExit(1)

    print("\n=== 2. Main benchmark behavior ===")

    try:
        benchmark = json.loads(
            (ROOT / "eval_questions_v2.json").read_text(encoding="utf-8")
        )
        questions = (
            benchmark["questions"]
            if isinstance(benchmark, dict)
            else benchmark
        )
    except Exception as exc:
        record("Load main benchmark", False, str(exc))
        raise SystemExit(1)

    question_map = {item["id"]: item["question"] for item in questions}
    record(
        "Main benchmark contains expected IDs",
        set(question_map) == set(EXPECTED_STATUSES),
        f"{len(questions)} questions loaded",
    )

    for question_id, expected_status in EXPECTED_STATUSES.items():
        question = question_map.get(question_id)

        if question is None:
            record(f"{question_id} status", False, "question missing")
            continue

        try:
            actual = answer_operational_question(question)
        except Exception as exc:
            record(f"{question_id} execution", False, repr(exc))
            continue

        status_ok = actual.get("status") == expected_status
        record(
            f"{question_id} status",
            status_ok,
            f"expected={expected_status}, actual={actual.get('status')}",
        )

        if status_ok and question_id in EXPECTED_RESULTS:
            result_ok = results_equal(
                actual.get("result"),
                EXPECTED_RESULTS[question_id],
            )
            record(
                f"{question_id} result",
                result_ok,
                "unordered rows compared" if result_ok else
                f"expected={EXPECTED_RESULTS[question_id]!r}; "
                f"actual={actual.get('result')!r}",
            )

    print("\n=== 3. Additional paraphrase checks ===")

    for index, (question, reference_id) in enumerate(PARAPHRASES, start=1):
        try:
            actual = answer_operational_question(question)
            status_ok = actual.get("status") == "answered"
            result_ok = (
                status_ok
                and results_equal(
                    actual.get("result"),
                    EXPECTED_RESULTS[reference_id],
                )
            )
            record(
                f"Paraphrase P{index}",
                result_ok,
                f"reference={reference_id}; question={question!r}; "
                f"actual_status={actual.get('status')}",
            )
        except Exception as exc:
            record(f"Paraphrase P{index}", False, repr(exc))

    print("\n=== Summary ===")
    print(f"Checks: {checks}")
    print(f"Failures: {failures}")

    if failures:
        print("FAIL: operational engine regression suite.")
        raise SystemExit(1)

    print("PASS: all automated checks passed.")


if __name__ == "__main__":
    main()
