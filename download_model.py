"""
Download and cache the Stable Audio Open 1.0 autoencoder weights from HuggingFace.

Usage:
    python download_model.py                    # uses HF_TOKEN from .env
    python download_model.py --token hf_xxx     # pass token directly
    python download_model.py --check            # just check if already cached

The model files are cached by huggingface_hub in its default cache directory
(~/.cache/huggingface/hub). Once downloaded, they're reused automatically —
no need to download again even across projects.
"""

import argparse
import os
import sys

REPO_ID = "stabilityai/stable-audio-open-1.0"
FILES = ["model_config.json", "model.safetensors"]


def get_token(cli_token: str | None = None) -> str:
    """Resolve HF token from CLI arg, .env file, or environment."""
    if cli_token:
        return cli_token

    # Try loading from .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token = os.environ.get("HF_TOKEN")
    if not token:
        print(
            "❌ HF_TOKEN not found.\n"
            "   Option 1: Add it to .env       →  HF_TOKEN=hf_your_token\n"
            "   Option 2: Pass it directly      →  python download_model.py --token hf_xxx\n"
            "   Option 3: Set in environment    →  export HF_TOKEN=hf_xxx\n"
            "\n"
            "   Get a token at https://huggingface.co/settings/tokens\n"
            "   Then accept the license at https://huggingface.co/stabilityai/stable-audio-open-1.0"
        )
        sys.exit(1)
    return token


def check_cached() -> bool:
    """Check if model files are already in the HF cache."""
    try:
        from huggingface_hub import try_to_load_from_cache
        for fname in FILES:
            cached = try_to_load_from_cache(REPO_ID, fname)
            if cached is None or cached is False:
                return False
        return True
    except Exception:
        return False


def download(token: str) -> None:
    """Download model files to the HF cache."""
    from huggingface_hub import hf_hub_download, login

    # Login globally so all hf_hub_download calls are authenticated
    login(token=token, add_to_git_credential=False)

    print(f"Downloading {REPO_ID} …")
    for fname in FILES:
        print(f"  ↓ {fname} …", end=" ", flush=True)
        path = hf_hub_download(REPO_ID, filename=fname, repo_type="model")
        print(f"✓  ({path})")

    print(f"\n✅ Model cached. Files are in the huggingface_hub cache directory.")
    print(f"   They'll be reused automatically — no need to re-download.")


def main():
    parser = argparse.ArgumentParser(description="Download Stable Audio Open 1.0 autoencoder")
    parser.add_argument("--token", type=str, default=None, help="HuggingFace access token")
    parser.add_argument("--check", action="store_true", help="Just check if model is cached, don't download")
    args = parser.parse_args()

    if args.check:
        if check_cached():
            print("✅ Model is already cached.")
        else:
            print("❌ Model is NOT cached. Run: make download-model")
        sys.exit(0 if check_cached() else 1)

    # Check if already downloaded
    if check_cached():
        print("✅ Model already cached — nothing to download.")
        return

    token = get_token(args.token)
    download(token)


if __name__ == "__main__":
    main()
