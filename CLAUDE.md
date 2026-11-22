# LLM Product Analytics: Project Brief

This file is the working brief for Claude Code. Put it at the root of the `llm-product-analytics` repo as `CLAUDE.md` so Claude Code reads it at the start of every session.

Full guide (background, hiring context, later stages): https://claude.ai/artifact/HAS8o6gD6RdTz6yyHkNAfj

---

## 1. What this project is

One end-to-end analytics project on real AI-usage data, built as a public portfolio piece for product and growth data science roles at AI companies (Anthropic, OpenAI and similar).

The finished repo shows:

- SQL and data modeling (dbt on DuckDB, with tests)
- An LLM task classifier that is validated against hand labels before it is trusted
- Product analysis: engagement, retention, task mix, safety
- A causal study: difference-in-differences plus a simulated CUPED A/B test
- A live dashboard and a README written as a one-page memo

Owner: Arjun Narendran. About 8 to 10 hours a week, evenings and weekends.

## 2. Stages

| Stage | Week | Goal | Done when |
|---|---|---|---|
| 1. Setup and data | 1 | Repo, environment, both datasets in DuckDB, cost estimator | `make data` rebuilds the warehouse and `make estimate` prints a cost |
| 2. Data model | 2 | dbt staging, intermediate and mart models, tests, `metrics.md` | `dbt build` is all green |
| 3. Classifier | 3 | Taxonomy, 200 hand labels, Claude classifier, evaluation, sample run | Accuracy, kappa and confusion matrix are in the README |
| 4. Product analysis | 4 | Engagement, retention by first task, task mix vs Economic Index, toxicity | Four charts, each with a numeric finding, a caveat and a "so what" |
| 5. Causal study | 5 | Diff-in-diff on a model switch with placebo test; CUPED simulation and power analysis | One effect with a confidence interval and a checked assumption |
| 6. Dashboard and memo | 6 | Three-page Streamlit app from the marts; README memo | Live link works on a phone; memo cut by a third |
| 7. Ship | after | Pin repo, CI on `dbt build`, résumé line, interview walkthrough | Fresh clone runs end to end |

**Current stage: 1.** Only do Stage 1 work unless Arjun says otherwise.

## 3. Rules for Claude Code

### Money and the API key

- **Never ask for, print, log or commit the Anthropic API key.** It lives only in `.env` on Arjun's machine.
- **No calls to the Anthropic API in Stage 1.** The cost estimator is fully offline.
- From Stage 3 on, every script that calls the API must:
  - default to a dry run that prints request count and estimated dollars, then exits
  - require a `--run` flag and an interactive confirmation where the user types the estimated dollar amount
  - enforce a hard `--limit` on conversations per run
  - set `max_tokens` to 50 or less (output is a short JSON object)
  - use the Message Batches API for any run over 500 requests
  - log the actual input and output tokens from each response's `usage` field to `classify/usage_log.csv`
- Spend in steps: 10 conversations, then the 200 gold labels, then 2,000, then the full sample. Re-estimate from real logged usage after each step.
- Arjun's account-level guardrails (do not change these, just know they exist): prepaid credits only, auto-reload off, a dedicated Console workspace with a monthly spend limit.

### Data and privacy

- WildChat contains real people's messages. **Never commit raw text or individual examples.** Everything under `data/` is gitignored.
- Anything committed (notebooks, charts, README) shows aggregates only.
- Ask before any single download larger than 2 GB.

### Working style

- Small commits with clear messages, for example "Add WildChat sample loader with turn flattening". No giant "final" commits.
- Prefer simple, readable code over clever code. This repo will be read by hiring managers.
- When a choice affects later stages (table names, sampling, user id), explain it in one or two lines and record it in `data/README.md` or `DECISIONS.md`.
- Check real data before assuming a schema. Inspect columns and a few rows first, then write the loader.

## 4. Stage 1: Setup and data (detailed)

### 4.1 Environment

- Python 3.11+, managed with `uv`.
- Dependencies:

```
uv add duckdb dbt-duckdb pandas polars pyarrow datasets huggingface_hub anthropic statsmodels scipy streamlit plotly python-dotenv
```

- `.gitignore` must include, before the first commit: `.env`, `data/raw/`, `data/*.duckdb`, `data/*.duckdb.wal`, `.venv/`, `__pycache__/`, `.ipynb_checkpoints/`, `dbt/target/`, `dbt/logs/`.
- Add `.env.example` containing only `ANTHROPIC_API_KEY=` (empty).
- License: MIT.

### 4.2 Repo layout

```
llm-product-analytics/
├── CLAUDE.md            # this brief
├── README.md            # the memo (Stage 6); placeholder for now
├── DECISIONS.md         # short log of design choices
├── .env.example
├── Makefile
├── pyproject.toml
├── data/
│   ├── raw/             # gitignored downloads
│   ├── README.md        # sources, licenses, row counts, gaps
│   └── warehouse.duckdb # gitignored
├── ingest/
│   ├── load_wildchat.py
│   └── load_econ_index.py
├── dbt/                 # Stage 2
├── classify/
│   ├── prompt_template.txt
│   └── estimate_cost.py
├── analysis/            # Stages 4 and 5
└── app/                 # Stage 6
```

### 4.3 Datasets

| Dataset | Source | Notes |
|---|---|---|
| WildChat-1M | https://huggingface.co/datasets/allenai/WildChat-1M | About 838K conversations, Parquet, ODC-BY license. Fields include `conversation_hash`, `model`, `timestamp`, `conversation` (list of turns), `turn`, `language`, `toxic`, `redacted`, `openai_moderation`, `detoxify_moderation`, `country`, `state`, `hashed_ip`. |
| Anthropic Economic Index | https://huggingface.co/datasets/Anthropic/EconomicIndex | Aggregated Claude usage by task and occupation. Organized by release; CC-BY data. |

Verify the actual field names before writing the loaders. The list above is a starting point, not a contract.

### 4.4 Tasks

1. **Scaffold the repo**: layout, `.gitignore`, `.env.example`, `pyproject.toml`, MIT license, placeholder `README.md`, empty `DECISIONS.md`. Commit.

2. **`ingest/load_wildchat.py`**
   - List the dataset's Parquet files with `huggingface_hub` and download only a subset of shards into `data/raw/wildchat/`. Do not pull the whole dataset while building. A `--shards N` argument controls how many (default: enough for roughly 10% of conversations).
   - Flatten into two tables in `data/warehouse.duckdb`, schema `raw`:
     - `raw.conversations`: one row per conversation. `conversation_id` (from `conversation_hash`), `timestamp`, `model`, `language`, `country`, `state`, `hashed_ip`, `toxic`, `redacted`, `turn_count`, plus `first_user_message` (kept locally only, needed for the classifier in Stage 3).
     - `raw.turns`: one row per message. `conversation_id`, `turn_index`, `role`, `char_length`, `language`, `toxic`. No message text.
   - Keep the moderation score structs as-is in a separate `raw.moderation` table, or flatten the top-level category scores. Note the choice in `DECISIONS.md`.
   - Print row counts and the min and max timestamp at the end.

3. **`ingest/load_econ_index.py`**
   - List the files in the dataset repo, find the latest release folder, and download its task-level CSVs into `data/raw/econ_index/`. Do not hardcode a release date.
   - Load each CSV into `raw.econ_<name>` in the same DuckDB file.
   - Print which release was loaded and the row counts.

4. **`data/README.md`**: source links, licenses, which shards and release were loaded, row counts, date range, and known gaps. Include at least:
   - `hashed_ip` is a proxy for a user, not a real user id. Shared IPs merge people; changing IPs split one person into several.
   - The `toxic` flag comes from automated moderation, not human review.
   - The sample is a subset of shards; note whether shards are time-ordered, since that affects any time-series analysis.

5. **`classify/prompt_template.txt`**: a first draft of the classifier prompt with a placeholder taxonomy of 9 categories (coding; writing and editing; analysis and math; learning and explanation; creative and roleplay; advice; translation; business and admin; other), a one-line definition each, and an instruction to return `{"category": "...", "confidence": 0.0}`. Use `{first_user_message}` as the slot. This is a draft for cost estimation; it gets refined in Stage 3.

6. **`classify/estimate_cost.py`** (offline, no API key, no network)
   - Reads `raw.conversations` from DuckDB and samples N conversations (`--n`, default 50000).
   - Builds the exact prompt for each: template plus the first user message cut to 1,000 characters.
   - Estimates input tokens as characters divided by 4 (state clearly that this is an approximation) and assumes 30 output tokens per request.
   - Prints a table of estimated cost for N = 10, 200, 2,000, 20,000 and 50,000 at both standard and batch rates.
   - Rates live as constants at the top of the file with a comment to verify them at https://platform.claude.com/docs/en/about-claude/pricing before any real run. Starting values for `claude-haiku-5-5`, per million tokens: standard $0.10 input, $0.50 output; batch $0.05 input, $0.25 output.
   - Also prints the 50th, 90th and 99th percentile prompt length, so outliers are visible.

7. **`Makefile`**

```
setup:     uv sync
data:      rebuild data/warehouse.duckdb from scratch (both loaders)
estimate:  run classify/estimate_cost.py
clean:     delete data/warehouse.duckdb (keep raw downloads)
```

Stubs for later stages are fine: `models` (dbt build), `app` (streamlit run).

### 4.5 Stage 1 is done when

- [ ] `make setup && make data` rebuilds the warehouse from scratch without errors
- [ ] `select count(*) from raw.conversations` returns a number in DuckDB
- [ ] Economic Index tables are loaded and the release is recorded
- [ ] `data/README.md` lists sources, licenses, counts, date range and gaps
- [ ] `make estimate` prints the cost table, and the 50K batch estimate is in the low single-digit dollars
- [ ] No raw text, data files or secrets in git history (`git log --stat` to check)
- [ ] Several small commits, not one big one

## 5. Looking ahead (do not build yet)

- **Stage 2** will build `stg_conversations`, `stg_turns`, `stg_econ_tasks`, then `int_user_days`, `int_conversation_features`, then marts `fct_conversations`, `dim_users`, `fct_daily_metrics`, `fct_retention`. Choose Stage 1 column names that map cleanly to these.
- **Stage 3** needs `first_user_message` from `raw.conversations` and a random sample of 200 for hand labeling. Arjun labels those himself before seeing any model output.
- **Stage 5** needs the `model` column and timestamps at full fidelity to find a model switch date, so do not drop or bucket them.
