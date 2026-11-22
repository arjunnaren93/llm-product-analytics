# Decisions

A short log of design choices that affect later stages.

- **Python 3.12, managed with uv.** dbt does not reliably support 3.14 yet, so the project pins 3.12 in `.python-version`.
