# Held-Out Evaluation Results — v1

## Run details

- Evaluation: `heldout_v1`
- Run date: 2026-11-04 (IST)
- Started: `2026-11-03T18:43:50.850227Z`
- Finished: `2026-11-03T18:43:51.006928Z`
- Cases: 8
- Requests per case: 1
- Retries: 0
- Preflight: PASS
- Run status: completed
- Input hashes unchanged: true

## Overall result

**0/8 held-out cases passed.**

| Case | Expected category | Actual behaviour | Verdict |
|---|---|---|---|
| H1 | Answerable | unsupported_question | Wrongly unsupported |
| H2 | Answerable | unsupported_question | Wrongly unsupported |
| H3 | Answerable | Returned DEP-003, SVC-003, auth-api, staging, failed | Wrong answer |
| H4 | Answerable | unsupported_question | Wrongly unsupported |
| H5 | Answerable | unsupported_question | Wrongly unsupported |
| H6 | Answerable | unsupported_question | Wrongly unsupported |
| H7 | Answerable | unsupported_question | Wrongly unsupported |
| H8 | Unanswerable | unsupported_question instead of explicit unanswerable response | Wrongly unsupported |

## Case observations

- H1 expected ERR-003 and ERR-005 with timestamps.
- H2 expected ERR-003, ERR-004, ERR-005 and ERR-006.
- H3 expected SVC-001/payments-api and SVC-002/orders-api. The returned failed deployment for SVC-003/auth-api contradicts the expected result.
- H4 expected INC-100 and INC-102.
- H5 expected a count of 6.
- H6 expected INC-103, started at 2026-10-11T11:59:59Z.
- H7 expected SVC-003/auth-api in staging.
- H8 expected an explicit explanation that customer-impact evidence is absent. The engine returned a generic unsupported response.

## Safety observation

No unsafe test case was included in this held-out set. Therefore, this run does not establish general safety or prove that unsafe requests are handled correctly.

## Integrity and reproducibility

- Runner SHA-256: `e1ba79ee6cff75e1770ded0191f018cdcbf9be11c7007978bd7c88b5ea6e528c`
- Results SHA-256: `2f6414d55f46309c78cf284c82192b429d712914376d8c06257531bfc4aafdc0`

Input hashes before and after were identical:

| Input | SHA-256 |
|---|---|
| Engine | `0e74419e40bc4ff704de75bd7cbde1cde0e410aa237b9792a684c30be6d32d67` |
| App | `401bf2c0c8c963720487014aa7193a71796e6348fb7271689a45d1d779d47e33` |
| Database | `06e10a9dbd17eb47a9ed960296b62f164f38fb65aee9e6d1bdf2741e854729f3` |
| Held-out fixture | `bb71bf4a424bfdf83cc24a47093a3fc7b7aacdda90b2d836d7822154cdca5269` |

The held-out questions were written by the same author as the engine. Isolation from earlier development cannot be proven.

## Limitations

This evaluation uses sample data and fixed question phrasings against a rule-based query engine. It does not demonstrate performance with real users, arbitrary natural-language questions, production databases, or unseen operational environments.

## Conclusion

The held-out evaluation protocol completed successfully and preserved all four input hashes. However, the engine passed 0 of 8 held-out cases: seven were wrongly unsupported and one returned an incorrect result. Stage 1's held-out capability has therefore not been demonstrated.
