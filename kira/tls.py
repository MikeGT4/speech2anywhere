# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import hashlib
import re
import ssl
from functools import lru_cache
from pathlib import Path

import certifi

DENIED_ROOTS = frozenset({
    "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b",
})
_PEM_BLOCK = re.compile(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.S)


def _fingerprint(pem: str) -> str:
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()


@lru_cache(maxsize=1)
def context() -> ssl.SSLContext:
    bundle = Path(certifi.where()).read_text(encoding="utf-8")
    trusted = [pem for pem in _PEM_BLOCK.findall(bundle) if _fingerprint(pem) not in DENIED_ROOTS]
    return ssl.create_default_context(cadata="\n".join(trusted))
