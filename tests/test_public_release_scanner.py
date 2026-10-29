"""Safety checks for open-source publication guardrails."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_public_release import matches, unsafe_path  # noqa: E402


def test_detects_generated_token_like_strings():
    synthetic = ("sk-" + "a" * 31).encode()
    assert "OpenAI key" in matches(synthetic)


def test_detects_private_key_header():
    header = ("-----BEGIN " + "PRIVATE KEY-----").encode()
    assert "private key" in matches(header)


def test_does_not_flag_placeholder_or_fixture():
    assert matches(b"export OPENAI_API_KEY=your-server-side-key") == []
    assert matches(b"token_provider=lambda: secret") == []


def test_sensitive_file_names():
    assert unsafe_path(".env.production")
    assert unsafe_path("secrets.json")
    assert unsafe_path("dev/private.pem")
    assert unsafe_path("data/site.sqlite")
    assert not unsafe_path("examples/quickstart.py")
    assert not unsafe_path(".env.example.sample.txt")
