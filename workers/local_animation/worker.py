import argparse
import json
import os
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from services.ai.providers.local_svd import (
    MODEL_ID, MODEL_REVISION, require_disk_space, require_license, run_inference,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolated local non-commercial SVD worker")
    parser.add_argument("operation", choices=["download", "generate"])
    parser.add_argument("--model-directory", type=Path, default=Path(__file__).parent / "model")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    require_license()
    if args.operation == "download":
        from huggingface_hub import snapshot_download
        require_disk_space(args.model_directory, 6 * 1024**3)
        snapshot_download(
            MODEL_ID, revision=MODEL_REVISION, local_dir=str(args.model_directory),
            allow_patterns=[
                "model_index.json", "*/config.json", "scheduler/scheduler_config.json",
                "feature_extractor/preprocessor_config.json", "*/*.fp16.safetensors",
                "LICENSE.md", "README.md",
            ],
        )
        require_disk_space(args.model_directory, 0)
        print(json.dumps({"model_directory": str(args.model_directory), "revision": MODEL_REVISION}))
    else:
        if args.image is None or args.output is None:
            parser.error("--image and --output are required for generation")
        def terminate() -> None:
            print("Local SVD exceeded its 30-minute execution limit.", file=sys.stderr, flush=True)
            os._exit(124)
        watchdog = threading.Timer(1800, terminate)
        watchdog.daemon = True
        watchdog.start()
        try:
            print(json.dumps(run_inference(args.image, args.output, args.model_directory, args.seed)))
        finally:
            watchdog.cancel()


if __name__ == "__main__":
    main()
