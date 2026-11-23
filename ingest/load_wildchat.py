"""Download WildChat-1M shards from Hugging Face and load them into DuckDB."""

import argparse
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

REPO_ID = "allenai/WildChat-1M"
RAW_DIR = Path("data/raw/wildchat")

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

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=int, default=None,
                        help="How many shards to download (default: all 14)")
    args = parser.parse_args()

    paths = download_shards(args.shards)
    total_gb = sum(p.stat().st_size for p in paths) / 1e9
    print(f"Done: {len(paths)} shards, {total_gb:.2f} GB in {RAW_DIR}")


if __name__ == "__main__":
    main()