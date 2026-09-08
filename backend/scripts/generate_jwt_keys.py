"""
Nepal School Management System - JWT Key Generator
Generates RSA-2048 key pair for JWT signing (RS256)
"""

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def generate_keys():
    """Generate RSA-2048 key pair for JWT signing"""

    print("Generating RSA-2048 key pair for JWT signing...")

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Create keys directory
    keys_dir = PROJECT_ROOT / "keys"
    keys_dir.mkdir(exist_ok=True)

    # Save private key
    private_key_path = keys_dir / "jwt_private.pem"
    with open(private_key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    print(f"[OK] Private key saved: {private_key_path}")

    # Extract and save public key
    public_key = private_key.public_key()
    public_key_path = keys_dir / "jwt_public.pem"
    with open(public_key_path, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))

    print(f"[OK] Public key saved: {public_key_path}")

    print("\n[SUCCESS] JWT keys generated successfully!")
    print("\n[IMPORTANT]:")
    print("   - Keep jwt_private.pem secure and never commit to Git")
    print("   - The keys/ directory is already in .gitignore")
    print("   - For production, use AWS Secrets Manager or similar")

    return True


if __name__ == "__main__":
    try:
        generate_keys()
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Error generating keys: {str(e)}", file=sys.stderr)
        sys.exit(1)
