"""CLI tests via Typer's ``CliRunner``."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from askii import AskiiAuthError, AskiiServerError
from askii.cli._app import EXIT_AUTH, EXIT_SERVER, app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client_factory() -> Iterator[MagicMock]:
    """Patch ``_build_client`` so commands don't try to open real httpx clients."""
    with patch("askii.cli._app._build_client") as factory:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        instance.__exit__.return_value = None
        factory.return_value = instance
        yield instance


def test_version_command(runner: CliRunner) -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_missing_token_exits_with_auth_code(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASKII_TOKEN", raising=False)
    result = runner.invoke(app, ["keys", "list"])
    assert result.exit_code == EXIT_AUTH


def test_keys_list_json(runner: CliRunner, mock_client_factory: MagicMock) -> None:
    from askii import KeyInfo, ListKeysResponse

    mock_client_factory.keys.list.return_value = ListKeysResponse(
        user_id="u-1",
        keys=[KeyInfo(key_name="k1", key_alias="a", spend=0.0, models=["gpt-4o"], memory_enabled=False)],
    )
    result = runner.invoke(
        app,
        ["keys", "list", "--token", "jwt-1", "--output", "json"],
    )
    assert result.exit_code == 0, result.stderr
    body: Any = json.loads(result.stdout)
    assert body["user_id"] == "u-1"
    assert body["keys"][0]["key_name"] == "k1"


def test_keys_list_table(runner: CliRunner, mock_client_factory: MagicMock) -> None:
    from askii import KeyInfo, ListKeysResponse

    mock_client_factory.keys.list.return_value = ListKeysResponse(
        user_id="u-2",
        keys=[KeyInfo(key_name="kn", spend=1.0, models=[], memory_enabled=False)],
    )
    result = runner.invoke(app, ["keys", "list", "--token", "jwt-1"])
    assert result.exit_code == 0, result.stderr
    assert "u-2" in result.stdout
    assert "kn" in result.stdout


def test_keys_provision_unwraps_secret(runner: CliRunner, mock_client_factory: MagicMock) -> None:
    from askii import ProvisionKeyResponse

    mock_client_factory.keys.provision.return_value = ProvisionKeyResponse(
        api_key="sk-realrealreal12345",
        key_name="n",
        user_id="u",
    )
    result = runner.invoke(
        app,
        ["keys", "provision", "--token", "jwt-1", "--alias", "foo", "--duration-days", "30"],
    )
    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["api_key"] == "sk-realrealreal12345"


def test_keys_revoke_returns_json(runner: CliRunner, mock_client_factory: MagicMock) -> None:
    from askii import RevokeKeyResponse

    mock_client_factory.keys.revoke.return_value = RevokeKeyResponse(revoked=True, detail="ok")
    result = runner.invoke(app, ["keys", "revoke", "--token", "jwt-1", "--key", "alias"])
    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body == {"revoked": True, "detail": "ok"}


def test_keys_get_config(runner: CliRunner, mock_client_factory: MagicMock) -> None:
    from askii import KeyConfig

    mock_client_factory.keys.get_config.return_value = KeyConfig(key_name="n", models=[], memory_enabled=False)
    result = runner.invoke(app, ["keys", "get-config", "--token", "jwt-1", "--key", "alias"])
    assert result.exit_code == 0


def test_keys_update_model(runner: CliRunner, mock_client_factory: MagicMock) -> None:
    from askii import UpdateKeyModelResponse

    mock_client_factory.keys.update_model.return_value = UpdateKeyModelResponse(
        updated=True, key_name="n", models=["gpt-4o"], default_model="gpt-4o"
    )
    result = runner.invoke(
        app,
        [
            "keys",
            "update-model",
            "--token",
            "jwt-1",
            "--key",
            "alias",
            "-m",
            "gpt-4o",
            "--default-model",
            "gpt-4o",
        ],
    )
    assert result.exit_code == 0


def test_models_list_json(runner: CliRunner, mock_client_factory: MagicMock) -> None:
    from askii import AvailableModel, AvailableModelsResponse

    mock_client_factory.models.list.return_value = AvailableModelsResponse(models=[AvailableModel(model_name="gpt-4o")])
    result = runner.invoke(app, ["models", "list", "--token", "jwt-1", "--output", "json"])
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["models"][0]["model_name"] == "gpt-4o"


def test_auth_error_exit_code(runner: CliRunner, mock_client_factory: MagicMock) -> None:
    mock_client_factory.keys.list.side_effect = AskiiAuthError(401, "bad jwt")
    result = runner.invoke(app, ["keys", "list", "--token", "jwt-1"])
    assert result.exit_code == EXIT_AUTH


def test_server_error_exit_code(runner: CliRunner, mock_client_factory: MagicMock) -> None:
    mock_client_factory.keys.list.side_effect = AskiiServerError(500, "boom")
    result = runner.invoke(app, ["keys", "list", "--token", "jwt-1"])
    assert result.exit_code == EXIT_SERVER


def test_base_url_passes_through_to_config(runner: CliRunner) -> None:
    """--base-url should reach AskiiConfig (caught here via patching)."""
    seen: dict[str, Any] = {}

    def fake_from_env(**kwargs: Any) -> Any:
        seen.update(kwargs)
        from askii._cache.memory import InMemoryCache
        from askii._config import AskiiConfig

        return AskiiConfig(
            base_url=kwargs.get("base_url", "https://api.askii.test"),
            token=kwargs.get("token", "jwt"),
            cache=InMemoryCache(),
        )

    with (
        patch("askii.cli._app.AskiiConfig.from_env", side_effect=fake_from_env),
        patch("askii.cli._app.Askii") as askii_cls,
    ):
        instance = MagicMock()
        instance.__enter__.return_value = instance
        instance.__exit__.return_value = None
        instance.models.list.return_value = MagicMock(
            models=[],
            model_dump=lambda mode="json": {"models": []},
        )
        askii_cls.return_value = instance
        result = runner.invoke(
            app,
            ["models", "list", "--token", "jwt-1", "--base-url", "https://custom.test", "--output", "json"],
        )
        assert result.exit_code == 0, result.stderr
        assert seen["base_url"] == "https://custom.test"


def test_cli_help(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Askii platform CLI" in result.stdout
