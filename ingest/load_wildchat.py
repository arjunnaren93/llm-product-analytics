"""Download WildChat-1M shards from Hugging Face and load them into DuckDB."""

import argparse
from pathlib import Path
import duckdb

from huggingface_hub import HfApi, hf_hub_download

REPO_ID = "allenai/WildChat-1M"
RAW_DIR = Path("data/raw/wildchat")
WAREHOUSE = Path("data/warehouse.duckdb")
PARQUET_FILES = f"read_parquet('{RAW_DIR}/data/*.parquet')"
SAMPLE_RULE = "md5_number(hashed_ip) % 10 = 0"

CONVERSATIONS_SQL = f"""
create or replace table raw.conversations as
select
    conversation[1].turn_identifier as conversation_id,
    conversation_hash,
    hashed_ip,
    timestamp,
    model,
    language,
    country,
    state,
    toxic,
    redacted,
    turn as turn_count,
    conversation[1].content as first_user_message
from {PARQUET_FILES}
where {SAMPLE_RULE}
"""

TURNS_SQL = f"""
create or replace table raw.turns as
with flat as (
    select
        conversation[1].turn_identifier as conversation_id,
        generate_subscripts(conversation, 1) as turn_index,
        unnest(conversation) as msg
    from {PARQUET_FILES}
    where {SAMPLE_RULE}
)
select
    conversation_id,
    turn_index,
    msg.role as role,
    length(msg.content) as char_length,
    msg.language as language,
    msg.toxic as toxic,
    msg.timestamp as timestamp
from flat
"""

def list_shards():
    """Return the dataset's Parquet filenames, sorted."""
    files = HfApi().list_repo_files(REPO_ID, repo_type="dataset")
    return sorted(f for f in files if f.endswith(".parquet"))

def download_shards(n_shards=None):
    """Download the first n_shards files (all if None). Files already on disk are skipped."""
    shards = list_shards()[:n_shards]
    paths = []
    for i, name in enumerate(shards, start=1):
        print(f"[{i}/{len(shards)}] {name}")
        path = hf_hub_download(REPO_ID, name, repo_type="dataset", local_dir=RAW_DIR)
        paths.append(Path(path))
    return paths

def load_to_duckdb():
    """Build raw.conversations and raw.turns from the downloaded shards."""
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("create schema if not exists raw")
    print("Building raw.conversations ...")
    con.execute(CONVERSATIONS_SQL)
    print("Building raw.turns ...")
    con.execute(TURNS_SQL)

    con.sql("""
        select 'conversations' as table_name, count(*) as row_count,
               min(timestamp) as first_seen, max(timestamp) as last_seen
        from raw.conversations
        union all
        select 'turns', count(*), null, null from raw.turns
    """).show()
    con.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=int, default=None,
                        help="How many shards to download (default: all 14)")
    args = parser.parse_args()

    paths = download_shards(args.shards)
    total_gb = sum(p.stat().st_size for p in paths) / 1e9
    print(f"Done: {len(paths)} shards, {total_gb:.2f} GB in {RAW_DIR}")
    load_to_duckdb()


if __name__ == "__main__":
    main()