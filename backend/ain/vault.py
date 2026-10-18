"""At-rest encryption for stored analysis results (Fernet: AES-128-CBC + HMAC-SHA256).

The key comes from AIN_DATA_KEY. In development, when it is unset, one is generated once into
DATA_DIR/secret.key (gitignored). Losing the key makes every stored result unreadable.
"""

from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet

from ain import config


@lru_cache
def _fernet() -> Fernet:
    key = os.getenv("AIN_DATA_KEY", "").strip().encode()
    if not key:
        path = config.DATA_DIR / "secret.key"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(path, "xb") as f:
                    f.write(Fernet.generate_key())
            except FileExistsError:
                pass  # another worker created it first
        key = path.read_bytes().strip()
    try:
        return Fernet(key)
    except ValueError:
        raise RuntimeError("AIN_DATA_KEY must be a Fernet key (32 url-safe base64 bytes).") from None


def encrypt(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt(token: bytes) -> bytes:
    return _fernet().decrypt(token)
