# app/core/auth/password_service.py
import os
import hashlib
import base64
import hmac

class PasswordService:
    """
    Password hashing and verification service using PBKDF2 with SHA-256.
    Format: iterations.salt+hash (base64)
    """
    # Iteration count to increase cracking difficulty
    _ITERATIONS = 10000
    # Length of the derived key in bytes (256 bits)
    _KEY_SIZE = 32
    # Length of the salt in bytes (128 bits)
    _SALT_SIZE = 16

    """
    提供密码哈希和验证功能的服务类。
    """

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hashes a password with a random salt.

        :param password: Plaintext password
        :return: Hashed password in the format iterations.base64(salt+hash)
        """
        # Generate a random salt
        salt = os.urandom(PasswordService._SALT_SIZE)
        # Derive the hash
        derived_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            PasswordService._ITERATIONS,
            dklen=PasswordService._KEY_SIZE
        )
        # Combine salt and hash, then encode
        hash_bytes = salt + derived_key
        return f"{PasswordService._ITERATIONS}.{base64.b64encode(hash_bytes).decode('utf-8')}"

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verifies a password against the stored hash.

        :param password: Plaintext password to verify
        :param hashed_password: Stored hash in the format iterations.base64(salt+hash)
        :return: True if match, False otherwise
        """
        try:
            iterations_str, b64_hash = hashed_password.split('.', 1)
            iterations = int(iterations_str)
            hash_bytes = base64.b64decode(b64_hash)
        except (ValueError, IndexError, base64.binascii.Error):
            # Incorrect format
            return False

        # Extract salt and original hash
        salt = hash_bytes[:PasswordService._SALT_SIZE]
        original_hash = hash_bytes[PasswordService._SALT_SIZE:]

        # Derive hash from input password
        test_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            iterations,
            dklen=len(original_hash)
        )

        # Constant-time comparison
        return hmac.compare_digest(original_hash, test_hash)
