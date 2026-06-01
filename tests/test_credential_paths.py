"""S3.3: credentials_json() must honor the CREDENTIALS_JSON_FILE env override
so the secret can live outside the repo, falling back to the in-repo default."""

from lib import credential_paths


def test_credentials_json_honors_env_override(monkeypatch, tmp_path):
    external = tmp_path / "secrets" / ".credentials.json"
    monkeypatch.setenv("CREDENTIALS_JSON_FILE", str(external))

    result = credential_paths.credentials_json()

    assert result == external.expanduser().resolve()


def test_credentials_json_falls_back_to_repo_default(monkeypatch):
    monkeypatch.delenv("CREDENTIALS_JSON_FILE", raising=False)

    result = credential_paths.credentials_json()

    assert result.name == ".credentials.json"
    assert result.parent.name == "config"
