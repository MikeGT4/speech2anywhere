# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import json
import os
import sys
import threading
import traceback

from huggingface_hub import constants, snapshot_download

from kira import progress as prog

HTTP_CHUNK = 1024 * 1024


def _send(**fields) -> None:
    sys.stdout.write(json.dumps(fields) + "\n")
    sys.stdout.flush()


def fetch(repo_id: str, target: str, patterns: list[str]) -> int:
    throttle = prog.Throttle()

    def report(done: int, total: int) -> None:
        if total > 0 and throttle.due(force=done >= total):
            _send(done=done, total=total)

    constants.DOWNLOAD_CHUNK_SIZE = HTTP_CHUNK
    try:
        path = snapshot_download(
            repo_id=repo_id,
            local_dir=target,
            allow_patterns=patterns,
            tqdm_class=prog.byte_progress_class(report),
        )
    except Exception as exc:
        _send(error=f"{type(exc).__name__}: {exc}", trace=traceback.format_exc())
        return 1
    _send(path=str(path))
    return 0


def _end_with_parent() -> None:
    try:
        os.read(0, 1)
    except OSError:
        return
    os._exit(1)


def main(argv: list[str]) -> int:
    threading.Thread(target=_end_with_parent, daemon=True).start()
    repo_id, target, *patterns = argv
    return fetch(repo_id, target, patterns)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
