# -*- coding: utf-8 -*-
"""
Crypto utilities for key format conversion.
"""

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    serialization = None
    default_backend = None


def ensure_pkcs1_format(private_key_string: str) -> str:
    """
    Receive a private key string of unknown format and ensure the output is
    in PKCS#1 format.

    Supported input formats:
    - PKCS#1 PEM format
    - PKCS#8 PEM format

    Args:
        private_key_string: A string containing the private key (PEM format
        or pure Base64)

    Returns:
        A string containing the private key in PKCS#1 PEM format.

    Raises:
        ImportError: Raised when the cryptography library is not installed.
        ValueError: Raised when the private key string is invalid or empty.
    """
    # Check if cryptography library is available
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ImportError(
            "Please install the cryptography library: pip "
            "install cryptography",
        )

    if not private_key_string or not private_key_string.strip():
        raise ValueError("The private key string cannot be empty.")

    key_string = private_key_string.strip()

    try:
        # Try to load directly as PEM format
        if "-----BEGIN" in key_string:
            private_key = serialization.load_pem_private_key(
                data=key_string.encode("utf-8"),
                password=None,
                backend=default_backend(),
            )
        else:
            # If it's pure Base64, first try PKCS#8 format
            clean_base64 = "".join(key_string.split())

            try:
                # Attempt PKCS#8 format PEM wrapping
                pkcs8_pem = (
                    f"-----BEGIN {'PRIVATE'} {'KEY'}-----\n"
                    f"{clean_base64}\n-----END {'PRIVATE'} {'KEY'}-----"
                )
                private_key = serialization.load_pem_private_key(
                    data=pkcs8_pem.encode("utf-8"),
                    password=None,
                    backend=default_backend(),
                )
            except Exception:
                # If PKCS#8 fails, try PKCS#1 format PEM wrapping
                pkcs1_pem = (
                    f"-----BEGIN RSA {'PRIVATE'} {'KEY'}-----\n"
                    f"{clean_base64}\n-----END RSA {'PRIVATE'} {'KEY'}-----"
                )
                private_key = serialization.load_pem_private_key(
                    data=pkcs1_pem.encode("utf-8"),
                    password=None,
                    backend=default_backend(),
                )

        # Force output in PKCS#1 format (Traditional OpenSSL format)
        pkcs1_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        return pkcs1_pem.decode("utf-8")

    except Exception as e:
        # If loading or conversion fails (e.g., the key is corrupted),
        # raise an exception
        raise ValueError(
            f"Failed to parse or convert the provided private key. Please "
            f"check if it is valid: {e}",
        ) from e
