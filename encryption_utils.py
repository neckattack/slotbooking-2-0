"""
Encryption utilities for user email password storage.
Uses Fernet (symmetric encryption) with key from EMAIL_ENCRYPTION_KEY env var.
"""
import os
from cryptography.fernet import Fernet


def get_cipher():
    """Get Fernet cipher from EMAIL_ENCRYPTION_KEY env var."""
    key = os.environ.get('EMAIL_ENCRYPTION_KEY')
    if not key:
        raise RuntimeError("EMAIL_ENCRYPTION_KEY not set in environment")
    return Fernet(key.encode())


def encrypt_password(plaintext: str) -> str:
    """Encrypt a password and return base64-encoded ciphertext."""
    if not plaintext:
        return ""
    cipher = get_cipher()
    encrypted = cipher.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_password(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext and return plaintext password."""
    if not ciphertext:
        return ""
    cipher = get_cipher()
    decrypted = cipher.decrypt(ciphertext.encode())
    return decrypted.decode()
