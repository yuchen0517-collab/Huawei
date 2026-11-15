from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any


class SessionStoreError(Exception):
    pass


class SessionStoreNotFound(SessionStoreError):
    pass


class InvalidSessionId(SessionStoreError):
    pass


class SessionStoreBeforeReplace(SessionStoreError):
    pass


class SessionStoreCommitUnknown(SessionStoreError):
    pass


def canonical_json(document: dict[str, Any]) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,

        separators=(",", ":"),
        allow_nan=False,
    )


class SessionStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path_for(self, session_id: str) -> Path:
        if not isinstance(session_id, str):
            raise InvalidSessionId()
        try:
            parsed = uuid.UUID(session_id)
        except (ValueError, AttributeError) as exc:
            raise InvalidSessionId() from exc
        if str(parsed) != session_id:
            raise InvalidSessionId()
        return self.root / f"{session_id}.json"

    def read(self, session_id: str) -> dict[str, Any]:
        path = self.path_for(session_id)
        try:
            with path.open("r", encoding="utf-8") as handle:
                document = json.load(handle)
        except FileNotFoundError as exc:
            raise SessionStoreNotFound() from exc
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SessionStoreError() from exc
        if not isinstance(document, dict):
            raise SessionStoreError()
        return document

    def write(self, document: dict[str, Any]) -> None:
        if not isinstance(document, dict):
            raise SessionStoreBeforeReplace()
        session_id = document.get("session_id")
        path = self.path_for(session_id)
        temporary_path = None
        replaced = False
        try:
            payload = canonical_json(document)
            self.root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=f".{session_id}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            replaced = True
            try:
                reread = self.read(session_id)
                if canonical_json(reread) != payload:
                    raise ValueError()
                self._sync_directory()
            except Exception as exc:
                raise SessionStoreCommitUnknown() from exc
        except SessionStoreCommitUnknown:
            raise
        except Exception as exc:
            raise SessionStoreBeforeReplace() from exc
        finally:
            if temporary_path is not None and not replaced:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _sync_directory(self) -> None:
        try:
            descriptor = os.open(self.root, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)