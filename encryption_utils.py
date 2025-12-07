"""
Encryption utilities for user email password storage.
Uses Fernet (symmetric encryption) with key from EMAIL_ENCRYPTION_KEY env var.
"""
import os
from cryptography.fernet import Fernet


def get_cipher():
    """Get Fernet cipher from EMAIL_ENCRYPTION_KEY env var.

    Akzeptiert sowohl str als auch bytes als Key, um Laufzeitfehler wie
    "'bytes' object has no attribute 'encode'" zu vermeiden.
    """
    key = os.environ.get('EMAIL_ENCRYPTION_KEY')
    if not key:
        raise RuntimeError("EMAIL_ENCRYPTION_KEY not set in environment")
    # Falls der Key bereits als bytes vorliegt, direkt verwenden
    if isinstance(key, (bytes, bytearray)):
        return Fernet(bytes(key))
    # Normalfall: String aus Env-Variable
    return Fernet(key.encode())


def encrypt_password(plaintext: str) -> str:
    """Encrypt a password and return base64-encoded ciphertext."""
    if not plaintext:
        return ""
    cipher = get_cipher()
    encrypted = cipher.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_password(ciphertext) -> str:
    """Decrypt a base64-encoded ciphertext and return plaintext password.

    Akzeptiert sowohl str als auch bytes, um Fehler wie
    "'bytes' object has no attribute 'encode'" zu vermeiden.
    """
    if not ciphertext:
        return ""
    cipher = get_cipher()
    # Falls der Ciphertext bereits bytes ist, direkt verwenden
    if isinstance(ciphertext, (bytes, bytearray)):
        decrypted = cipher.decrypt(bytes(ciphertext))
    else:
        decrypted = cipher.decrypt(str(ciphertext).encode())
    return decrypted.decode()
