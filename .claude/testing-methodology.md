# Testing Methodology with Claude Code

## 1. Describe behavior, not code

When adding a feature, describe what it should *do*, not what to build. Claude will write the test and the implementation together, anchoring behavior by default rather than as an afterthought.

> "Add an endpoint that returns items expiring within 7 days. Items with no expiry date should be excluded."

## 2. Wire a test-run hook

Use `/update-config` to add a hook that runs the test suite automatically after Claude edits Python files. Failures surface immediately in the same turn.

> `/update-config` — run `pytest tests/ -x -q` after every file save

The `-x` flag (stop on first failure) keeps the feedback loop tight.

## 3. Commit tests with the code, never separately

If a commit touches `app/routers/items.py`, `tests/test_items.py` should be in the same commit. Be explicit: "write the test and the implementation."

## 4. Periodic gap audits

Every few features, ask: **"Is my test suite adequate?"** Claude reads the source, maps error paths and branches, and surfaces dead code, untested endpoints, and missing constraint tests. Do it before a milestone or PR, not just at the end.

## 5. Use `/code-review` before pushing

`/code-review` (or `/code-review ultra` for a deeper pass) catches logic bugs that tests don't cover yet. Tests verify behavior; code review catches things you didn't think to test.
