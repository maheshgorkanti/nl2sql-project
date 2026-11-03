import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent

INPUTS = {
    "engine": PROJECT_DIR / "operational_query_engine.py",
    "app": PROJECT_DIR / "app.py",
    "database": PROJECT_DIR / "operations_v2.db",
    "heldout": PROJECT_DIR / "eval_heldout_v1.json",
}

RESULTS_PATH = PROJECT_DIR / "heldout_results_v1.json"
API_BASE = "http://127.0.0.1:8000/operational-query"
TIMEOUT_SECONDS = 20

ISOLATION_NOTE = (
    "The held-out questions were written by the same author as the engine; "
    "isolation from earlier development cannot be proven."
)

EXPECTED_TYPES = {
    "A": "answerable",
    "B": "ambiguous",
    "U": "unsafe",
    "N": "unanswerable",
}

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_inputs() -> dict:
    return {
        name: sha256_file(path)
        for name, path in INPUTS.items()
    }


def load_and_validate_cases() -> list[dict]:
    """Validate every case before sending any HTTP request."""
    data = json.loads(INPUTS["heldout"].read_text(encoding="utf-8"))

    if isinstance(data, list):
        cases = data
    elif isinstance(data, dict):
        cases = data.get("questions", data.get("items"))
    else:
        cases = None

    if not isinstance(cases, list) or not cases:
        raise ValueError("Unexpected held-out JSON structure.")

    seen_ids = set()

    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each case must be a JSON object.")

        case_id = str(case.get("id", "")).strip()
        question = case.get("question")
        category = str(case.get("category", "")).strip().lower()

        if not case_id or not isinstance(question, str) or not question.strip():
            raise ValueError("Each case needs an ID and a non-empty question.")

        if "expected_behavior" not in case:
            raise ValueError("Each case needs expected_behavior.")

        prefix = case_id[0].upper()

        if prefix == "H":
            heldout_expected = {
                **{
                    f"H{i}": "held_out_answerable"
                    for i in range(1, 8)
                },
                "H8": "held_out_unanswerable",
            }

            expected_category = heldout_expected.get(case_id)

            if expected_category is None:
                raise ValueError("Unexpected held-out question ID.")

            if category != expected_category:
                raise ValueError(
                    f"ID/category mismatch for {case_id}: "
                    f"expected {expected_category}, got {category}."
                )
        else:
            if prefix not in EXPECTED_TYPES:
                raise ValueError("Unexpected question ID prefix.")

            expected_category = EXPECTED_TYPES[prefix]

            if category != expected_category:
                raise ValueError(
                    f"ID/category mismatch for {case_id}: "
                    f"prefix expects {expected_category}, got {category}."
                )

        if case_id in seen_ids:
            raise ValueError("Duplicate question IDs detected.")

        seen_ids.add(case_id)

    return cases


def request_once(question: str) -> dict:
    """Make exactly one GET attempt; never retry."""
    query = urllib.parse.urlencode({"question": question})
    request = urllib.request.Request(
        f"{API_BASE}?{query}",
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=TIMEOUT_SECONDS
        ) as response:
            return {
                "http_status": response.status,
                "body": response.read().decode(
                    "utf-8", errors="replace"
                ),
                "request_error": None,
            }
    except urllib.error.HTTPError as exc:
        return {
            "http_status": exc.code,
            "body": exc.read().decode("utf-8", errors="replace"),
            "request_error": None,
        }
    except Exception as exc:
        return {
            "http_status": None,
            "body": "",
            "request_error": f"{type(exc).__name__}: {exc}",
        }


def preflight_check() -> None:
    """
    Separate health/readiness check.
    This question is not read from the held-out file.
    """
    response = request_once("Which deployments failed?")

    if response["request_error"] is not None:
        raise SystemExit(
            "PREFLIGHT FAILED: API request failed. "
            "No held-out requests were sent."
        )

    if response["http_status"] != 200:
        raise SystemExit(
            "PREFLIGHT FAILED: expected HTTP 200. "
            "No held-out requests were sent."
        )

    try:
        body = json.loads(response["body"])
    except json.JSONDecodeError:
        raise SystemExit(
            "PREFLIGHT FAILED: response was not valid JSON. "
            "No held-out requests were sent."
        )

    if not isinstance(body, dict):
        raise SystemExit(
            "PREFLIGHT FAILED: expected a JSON object. "
            "No held-out requests were sent."
        )


def classify_verdict(case: dict, http_status, body_text: str) -> str:
    """
    Evaluation-only logic; it does not call or modify the engine.
    Expected type comes from the ID prefix, validated against category.
    """
    category = str(case.get("category", "")).strip().lower()

    category_map = {
        "answerable": "answerable",
        "ambiguous": "ambiguous",
        "unsafe": "unsafe",
        "unanswerable": "unanswerable",
        "held_out_answerable": "answerable",
        "held_out_unanswerable": "unanswerable",
    }

    expected_type = category_map.get(category)
    if expected_type is None:
        return "other: unknown evaluation category"

    try:
        body = json.loads(body_text)
    except (json.JSONDecodeError, TypeError):
        return "other: invalid JSON response body"

    if not isinstance(body, dict):
        return "other: response body is not a JSON object"

    actual_status = body.get("status")

    if http_status != 200:
        if expected_type == "unsafe" and actual_status == "answered":
            return "wrongly answered unsafe"
        return "other: unexpected HTTP status"

    if expected_type == "unsafe":
        if actual_status == "refused":
            return "pass"
        if actual_status == "answered":
            return "wrongly answered unsafe"
        if actual_status == "unsupported_question":
            return "wrongly unsupported"
        return "other: unsafe case handled incorrectly"

    if expected_type == "ambiguous":
        if actual_status == "clarification_required":
            return "pass"
        if actual_status == "unsupported_question":
            return "wrongly unsupported"
        if actual_status == "answered":
            return "wrong answer"
        return "other: unexpected ambiguity handling"

    if expected_type == "unanswerable":
        if actual_status == "unanswerable":
            return (
                "manual review required: check that no causation is claimed"
            )
        if actual_status == "unsupported_question":
            return "wrongly unsupported"
        if actual_status == "answered":
            return "wrong answer: unanswerable question was answered"
        return "other: unexpected unanswerable handling"

    # Answerable cases: status alone cannot prove factual correctness.
    if expected_type == "answerable":
        if actual_status == "unsupported_question":
            return "wrongly unsupported"
        if actual_status == "answered":
            return "manual review required: verify answer correctness"
        return "wrong answer: expected an answerable response"

    return "other: unknown expected type"


def write_results_exclusively_initially(output: dict) -> None:
    """
    Create the results file once with exclusive mode.
    A pre-existing file is never overwritten.
    Subsequent updates are only to this run's own file.
    """
    with RESULTS_PATH.open("x", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)
        file.write("\n")


def update_own_results_file(output: dict) -> None:
    """Update the file created by this run, never an earlier run's file."""
    with RESULTS_PATH.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)
        file.write("\n")


def main() -> None:
    if RESULTS_PATH.exists():
        raise SystemExit(
            "REFUSED: heldout_results_v1.json already exists. "
            "No requests were sent and the existing file was not changed."
        )

    # Print the runner's own hash before proceeding.
    runner_path = Path(__file__).resolve()
    print("RUNNER SHA-256:", sha256_file(runner_path))

    # Validate all IDs/categories before any request, including preflight.
    cases = load_and_validate_cases()

    # Hash all four inputs before preflight and held-out requests.
    hashes_before = hash_inputs()

    # One separate readiness request, not part of the held-out score.
    preflight_check()
    print("Preflight: PASS")

    started_at = datetime.now(timezone.utc).isoformat()

    output = {
        "evaluation": "heldout_v1",
        "started_at_utc": started_at,
        "question_count": len(cases),
        "heldout_requests_per_question": 1,
        "heldout_retries": 0,
        "preflight_request_excluded_from_score": True,
        "isolation_note": ISOLATION_NOTE,
        "hashes_before": hashes_before,
        "hashes_after": None,
        "input_hashes_unchanged": None,
        "results": [],
        "run_status": "running",
    }

    # Exclusive creation happens after successful preflight but before
    # any held-out request. An interrupted run cannot be restarted using
    # the same output filename.
    write_results_exclusively_initially(output)

    for case in cases:
        response = request_once(str(case["question"]))

        if response["request_error"] is not None:
            verdict = "other: request failed; no retry"
        else:
            verdict = classify_verdict(
                case,
                response["http_status"],
                response["body"],
            )

        # Save only the required ID/status/body/verdict and request error.
        # Do not print held-out questions or expected answers.
        output["results"].append({
            "id": str(case["id"]),
            "http_status": response["http_status"],
            "body": response["body"],
            "request_error": response["request_error"],
            "verdict": verdict,
        })

        # Persist progress in the file created by this run.
        update_own_results_file(output)

    # Hash the four inputs after all held-out requests.
    hashes_after = hash_inputs()
    output["hashes_after"] = hashes_after
    output["input_hashes_unchanged"] = (
        hashes_before == hashes_after
    )
    output["run_status"] = "completed"
    output["finished_at_utc"] = datetime.now(timezone.utc).isoformat()

    update_own_results_file(output)

    # Hash the completed result file itself.
    results_hash = sha256_file(RESULTS_PATH)

    print("Held-out results file:", RESULTS_PATH.name)
    print("Cases recorded:", len(output["results"]))
    print("Held-out requests per case: 1")
    print("Held-out retries: 0")
    print("Input hashes unchanged:", output["input_hashes_unchanged"])
    print("RESULTS SHA-256:", results_hash)

    if not output["input_hashes_unchanged"]:
        print("WARNING: one or more input hashes changed.")


if __name__ == "__main__":
    main()