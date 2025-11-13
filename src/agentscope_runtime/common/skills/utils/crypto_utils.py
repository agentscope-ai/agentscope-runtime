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
    接收一个未知格式的私钥字符串，并确保返回的是 PKCS#1 格式的字符串。

    支持的输入格式：
    - PKCS#1 PEM 格式
    - PKCS#8 PEM 格式


    Args:
        private_key_string: 包含私钥的字符串 (PEM格式或纯Base64)

    Returns:
        包含 PKCS#1 PEM 格式私钥的字符串。

    Raises:
        ImportError: 当cryptography库未安装时抛出
        ValueError: 当私钥字符串无效或为空时抛出
    """
    # 检查cryptography库是否可用
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ImportError("请安装cryptography库: pip install cryptography")

    if not private_key_string or not private_key_string.strip():
        raise ValueError("输入的私钥字符串不能为空。")

    key_string = private_key_string.strip()

    try:
        # 尝试直接作为PEM格式加载
        if "-----BEGIN" in key_string:
            private_key = serialization.load_pem_private_key(
                data=key_string.encode("utf-8"),
                password=None,
                backend=default_backend(),
            )
        else:
            # 如果是纯Base64，先尝试作为PKCS#8格式
            # 清理Base64字符串（移除空白字符）
            clean_base64 = "".join(key_string.split())

            try:
                # 先尝试PKCS#8格式的PEM包装
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
                # 如果PKCS#8失败，尝试PKCS#1格式的PEM包装
                pkcs1_pem = (
                    f"-----BEGIN RSA {'PRIVATE'} {'KEY'}-----\n"
                    f"{clean_base64}\n-----END RSA {'PRIVATE'} {'KEY'}-----"
                )
                private_key = serialization.load_pem_private_key(
                    data=pkcs1_pem.encode("utf-8"),
                    password=None,
                    backend=default_backend(),
                )

        # 强制以 PKCS#1 格式输出 (Traditional OpenSSL format)
        pkcs1_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        return pkcs1_pem.decode("utf-8")

    except Exception as e:
        # 如果加载或转换失败 (例如，密钥本身已损坏)，则抛出异常。
        raise ValueError(
            f"无法解析或转换提供的私钥，请检查其是否为有效的密钥: {e}",
        ) from e
