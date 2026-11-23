# Decisions

A short log of design choices that affect later stages.

- **Python 3.12, managed with uv.** dbt does not reliably support 3.14 yet, so the project pins 3.12 in `.python-version`.
- **WildChat sample: all 14 shards, 10% of users.** The shards are in time order (shard 0 covers only Apr–May 2023), so taking the first few would leave too little time for retention analysis and no model switch to study. Instead we download every shard and keep a user when `hash(hashed_ip) % 10 = 0`. That keeps each sampled user's full history across Apr 2023–Apr 2024 and gives the same sample on every run.
  - Caveat: `hashed_ip` is a proxy, not a real user id. Shared IPs merge people and changing IPs split one person, so "users" and retention are approximate.
- **conversation_id = first message's `turn_identifier`, not `conversation_hash`.** The hash is built from the text, so identical chats (e.g. "hi") share one: 837,989 conversations but only 826,319 hashes. The first turn_identifier is unique for every conversation.
- **Sample rule uses `md5_number(hashed_ip) % 10 = 0`** rather than DuckDB's `hash()`, because MD5 gives the same result in every DuckDB version, so the sample is reproducible.