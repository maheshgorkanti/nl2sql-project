# NL2SQL - Read-Only Operational Evidence Query Engine

## Project Overview

This project is a Python API that allows users to ask supported database questions in natural language and receive structured results.

Its primary direction is operational debugging: retrieving evidence from operational data, including incidents, services, deployments, and error events.

The project prioritizes:

- Read-only database access
- Evidence-based query results
- Deterministic and transparent query handling
- Explicit handling of unsupported and unanswerable questions
- Avoiding invented results and unsupported conclusions

The current implementation uses deterministic, rule-based question patterns. It does not provide unrestricted natural-language-to-SQL generation.

## Tech Stack

- Python
- FastAPI
- SQLite
- Pandas
- Uvicorn

## Project Architecture

The project currently contains two separate query paths:

| Component | Purpose |
|---|---|
| `/query` | Existing orders and sales database queries |
| `/operational-query` | Operational debugging queries against `operations_v2.db` |
| `sql_engine.py` | Existing sales query engine |
| `operational_query_engine.py` | Operational evidence query engine |
| `app.py` | FastAPI application exposing both endpoints |

## Operational Debugging Engine

The operational query engine is designed to help investigate operational data by retrieving relevant evidence from a structured database.

### Operational Data

The database contains:

- Services and their environments
- Incidents, start times, resolution times, and statuses
- Deployments, versions, timestamps, and deployment statuses
- Error events, severity levels, timestamps, and associated incident identifiers

### Implemented Question Patterns

The current implementation includes deterministic rules for selected questions involving:

- Error counts grouped by service within the benchmark time window
- Incidents starting within the benchmark time window
- Error-count comparisons before and after supported deployments
- Deployments with failed status
- Clarification requests for ambiguous questions
- Refusal of tested unsafe requests
- Handling of questions that cannot be answered from the available schema

These are specific implemented patterns, not general support for arbitrary natural-language questions.

### Benchmark Time Window

The frozen operational dataset uses this UTC reference window:

`2026-10-11T12:00:00Z` to `2026-10-12T12:00:00Z`

The interval follows the half-open convention `[start, end)`: the start is included and the end is excluded.

This is a fixed evaluation window, not a live monitoring period.

## Execution and Safety Design

The engine maps recognized questions to predefined SQL statements rather than executing SQL supplied by users.

The database reader uses:

- SQLite read-only access
- Query-only mode
- SQLite authorizer restrictions

These controls have passed the targeted checks performed in this project. They do not constitute proof against every possible SQL attack or a complete production security assessment.

## Verification and Evaluation Results

The project has been evaluated using automated regression checks, user-authored questions, and a separate held-out evaluation.

| Evaluation | Result |
|---|---:|
| Operational regression checks | 41/41 passed |
| User-authored evaluation questions | 3/5 |
| Held-out evaluation | 0/8 passed |

### Held-Out Evaluation Details

The held-out evaluation was completed on 2026-11-04 (IST).

- Preflight: passed
- Held-out cases: 8
- Requests per case: 1
- Retries: 0
- Input hashes unchanged: true
- Evaluation status: completed

Results:

- 7 cases were wrongly unsupported.
- 1 case returned an incorrect answer.
- 0 cases passed.

The engine returned a generic unsupported response for H8, even though the expected behaviour was to explain that customer-impact evidence was absent and classify the question as unanswerable.

The detailed case-by-case results are recorded in `eval_user_results_v1.md`, and the raw responses are preserved in `heldout_results_v1.json`.

### What These Results Demonstrate

The 41/41 result demonstrates that the tested operational regression checks passed.

The 3/5 result records the outcome of five user-authored questions.

The held-out result demonstrates that the current engine did not generalize successfully to the eight separately evaluated questions.

These measurements describe different evaluation sets and must not be combined into a single accuracy percentage.

## Limitations

The current evaluation and implementation have important limitations:

1. **Sample data:** The operational engine has been tested against a prepared SQLite dataset, not a live production environment.
2. **Rule-based matching:** Supported questions depend on predefined patterns and SQL mappings.
3. **Fixed phrasings:** The evaluation does not establish reliable handling of arbitrary ways users might express operational questions.
4. **Limited evaluation size:** The held-out evaluation contains only eight questions.
5. **No real-user validation:** The system has not been evaluated with a representative group of real operational engineers.
6. **General safety is unproven:** Targeted safety checks do not prove complete protection against every possible misuse or attack.
7. **Limited operational evidence:** The engine cannot answer questions when the required evidence is absent from the available database.

## Relationship to OPRXAI

This project is designed to plug in as a read-only evidence-query component within OPRXAI, an AI Incident Intelligence and Resolution Platform.

The intended relationship is to provide structured operational evidence that can support incident investigation and subsequent reasoning.

It is not currently integrated into OPRXAI.

## Existing Sales Query API

The existing `/query` endpoint remains a separate orders and sales query path using `company.db`.

Its tested question patterns include:

- Total sales
- Top 3 customers by total spending
- Average order value
- Number of orders
- Highest order amount

The existing implementation uses deterministic question patterns and read-only SQLite execution.

### Start the API

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

### Sales Query Endpoint

```text
GET /query?question=Total%20sales
```

### Operational Query Endpoint

```text
GET /operational-query
```

The operational endpoint accepts a natural-language question through its request body.

## Important Project Files

| File | Purpose |
|---|---|
| `app.py` | FastAPI application |
| `sql_engine.py` | Sales query engine |
| `operational_query_engine.py` | Operational query engine |
| `company.db` | Sales database |
| `operations_v2.db` | Operational database |
| `eval_questions_v2.json` | Main operational benchmark |
| `eval_heldout_v1.json` | Sealed held-out questions |
| `heldout_results_v1.json` | Raw held-out evaluation results |
| `eval_user_results_v1.md` | Held-out evaluation report |
| `test_operational_engine_v2.py` | Operational regression checks |
| `run_heldout_v1.py` | Held-out evaluation runner |

## Project Status

The project has an implemented read-only operational query engine, automated regression checks, and a completed held-out evaluation.

The regression checks passed, but the held-out evaluation exposed substantial limitations in question coverage and answer correctness.

The next development stage should address these limitations through a separately defined evaluation and improvement process. The sealed Stage 1 held-out questions must not be used as tuning examples.
