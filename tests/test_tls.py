# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import hashlib
import re
import ssl
from pathlib import Path

import certifi

from kira import tls

EMSIGN_ECC_ROOT_G3 = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"
_PEM = re.compile(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.S)


def _fingerprints(context: ssl.SSLContext) -> set[str]:
    return {hashlib.sha256(der).hexdigest() for der in context.get_ca_certs(binary_form=True)}


def _bundle_fingerprints() -> set[str]:
    text = Path(certifi.where()).read_text(encoding="utf-8")
    return {hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest() for pem in _PEM.findall(text)}


def test_emsign_ecc_root_g3_is_denied():
    assert EMSIGN_ECC_ROOT_G3 in tls.DENIED_ROOTS


def test_context_trusts_no_denied_root():
    assert not _fingerprints(tls.context()) & tls.DENIED_ROOTS


def test_context_keeps_every_other_root_of_the_bundle():
    assert _fingerprints(tls.context()) == _bundle_fingerprints() - tls.DENIED_ROOTS


def test_context_checks_certificate_and_hostname():
    context = tls.context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
