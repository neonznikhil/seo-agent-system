import pytest
import os
from unittest.mock import patch, MagicMock
from services.wordpress_service import WordPressService
from security import encrypt_secret, decrypt_secret

def test_wordpress_service_auth_resolution():
    """Verify that WordPressService robustly resolves credentials and avoids ciphertext leaks."""
    ws = WordPressService("44666e81-1d83-4801-be22-1cb72f39801a")
    user, pwd = ws._get_auth_tuple()
    
    assert user == "nikhil_d"
    assert pwd is not None
    assert len(pwd) > 0
    # Must NOT be a Fernet ciphertext
    assert not pwd.startswith("gAAAA")
    # Must NOT be masked with bullets
    assert "•" not in pwd


def test_multifernet_encryption_decryption():
    """Verify that MultiFernet can encrypt and decrypt secrets cleanly."""
    secret = "TestAppPassword123"
    enc = encrypt_secret(secret)
    assert enc.startswith("gAAAA")
    
    dec = decrypt_secret(enc)
    assert dec == secret


def test_undecryptable_ciphertext_never_returned():
    """Verify that undecryptable ciphertext returns empty string instead of leaking raw ciphertext."""
    fake_token = "gAAAAABqFakeUndecryptableCiphertextWithCorruptBytes1234567890abcdefghijklmnopqrstuvwxyz"
    dec = decrypt_secret(fake_token)
    assert dec == ""
