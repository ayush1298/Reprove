from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from reprove.github import GitHubAppAuth


def test_github_app_signs_short_lived_rs256_jwt():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    token = GitHubAppAuth("12345", pem).app_jwt(now=1_700_000_000)
    header, claims, signature = token.split(".")
    assert header and claims and signature
    assert "=" not in token

