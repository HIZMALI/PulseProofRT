"""OS-held workspace acquisition lock shared by CLI and HTTP worker processes."""
import contextlib
import os
from pathlib import Path

@contextlib.contextmanager
def acquisition_lock(workspace):
    path=Path(workspace)/"artifacts/acquisition.lock"
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a+b") as stream:
        if path.stat().st_size == 0:
            stream.write(b"0");stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Another experiment owns this workspace; wait for it to finish") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
