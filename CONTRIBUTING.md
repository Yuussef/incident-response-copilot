# Contributing

Use synthetic data only. Keep evidence collection tools read-only, preserve source IDs and timestamps,
and make deterministic behavior testable without an LLM. Run `uv run pytest` and
`npm --prefix frontend run build` before opening a pull request. Do not commit secrets, production
logs, customer data, or credentials.
