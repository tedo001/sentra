"""Secrets the console must keep between sessions: cloud keys, the backup passphrase.

A scheduled backup runs with nobody at the keyboard, so the passphrase that
encrypts it and the key that uploads it have to be on this machine. They are
never written into the preferences file in the clear:

* On Windows they are sealed with DPAPI (``CryptProtectData``) - only the same
  Windows account on the same machine can open them again.
* Elsewhere they are encrypted with a Fernet key kept in its own file, readable
  by the owner only (mode 0600).

Either way an administrator can clear a secret, and the Data & Backup page
shows only whether one is stored, never its value.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
from typing import Dict, Optional

from . import prefs

__all__ = ["Vault", "VAULT_FILE", "KEY_FILE"]

LOGGER = logging.getLogger("sif.vault")

VAULT_FILE = "vault.json"
KEY_FILE = "vault.key"


def _dpapi(data: bytes, protect: bool) -> bytes:  # pragma: no cover - Windows only
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    source = Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)),
                                         ctypes.POINTER(ctypes.c_char)))
    target = Blob()
    call = (ctypes.windll.crypt32.CryptProtectData if protect
            else ctypes.windll.crypt32.CryptUnprotectData)
    if not call(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)):
        raise OSError("DPAPI refused the secret")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


class Vault:
    """Named secrets, sealed at rest."""

    def __init__(self, directory: str = "") -> None:
        self.directory = directory or prefs.config_directory()
        self.path = os.path.join(self.directory, VAULT_FILE)
        self.windows = sys.platform.startswith("win")

    # -- sealing ---------------------------------------------------------------

    def _fernet(self):
        from cryptography.fernet import Fernet

        key_path = os.path.join(self.directory, KEY_FILE)
        if not os.path.exists(key_path):
            os.makedirs(self.directory, exist_ok=True)
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(Fernet.generate_key())
        with open(key_path, "rb") as handle:
            return Fernet(handle.read().strip())

    def _seal(self, value: str) -> str:
        data = value.encode("utf-8")
        if self.windows:  # pragma: no cover - Windows only
            return "dpapi:" + base64.b64encode(_dpapi(data, True)).decode("ascii")
        return "fernet:" + self._fernet().encrypt(data).decode("ascii")

    def _open(self, sealed: str) -> str:
        kind, _, body = sealed.partition(":")
        if kind == "dpapi":  # pragma: no cover - Windows only
            return _dpapi(base64.b64decode(body), False).decode("utf-8")
        if kind == "fernet":
            return self._fernet().decrypt(body.encode("ascii")).decode("utf-8")
        raise ValueError(f"unknown seal {kind!r}")

    # -- the file ----------------------------------------------------------------

    def _read(self) -> Dict[str, str]:
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as exc:  # noqa: BLE001 - an unreadable vault reads as empty
            LOGGER.warning("Ignoring unreadable vault (%s)", exc)
            return {}

    def _write(self, data: Dict[str, str]) -> None:
        os.makedirs(self.directory, exist_ok=True)
        temporary = self.path + ".tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        os.replace(temporary, self.path)

    # -- the interface -------------------------------------------------------------

    def put(self, name: str, value: str) -> None:
        data = self._read()
        if value:
            data[name] = self._seal(value)
        else:
            data.pop(name, None)
        self._write(data)

    def get(self, name: str) -> Optional[str]:
        sealed = self._read().get(name)
        if not sealed:
            return None
        try:
            return self._open(sealed)
        except Exception as exc:  # noqa: BLE001 - a secret from another machine or key
            LOGGER.warning("Could not open the stored secret %r (%s)", name, exc)
            return None

    def has(self, name: str) -> bool:
        return bool(self._read().get(name))

    def clear(self, name: str) -> None:
        self.put(name, "")
