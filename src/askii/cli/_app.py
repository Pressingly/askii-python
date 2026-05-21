"""``askii`` CLI implementation."""

from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Annotated, Any

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from askii import (
    Askii,
    AskiiAPIError,
    AskiiAuthError,
    AskiiConfig,
    AskiiError,
    AskiiServerError,
    AskiiTransportError,
    AskiiValidationError,
    __version__,
)
from askii.models import MemoryMode

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_AUTH = 2
EXIT_VALIDATION = 3
EXIT_TRANSPORT = 4
EXIT_SERVER = 5
EXIT_API = 6
EXIT_UNEXPECTED = 99

stdout = Console()
stderr = Console(stderr=True)


class OutputFmt(str, Enum):
    """How to render command output."""

    TABLE = "table"
    JSON = "json"


app = typer.Typer(no_args_is_help=True, add_completion=False, help="Askii platform CLI.")
keys_app = typer.Typer(no_args_is_help=True, help="Manage Askii virtual keys.")
models_app = typer.Typer(no_args_is_help=True, help="Inspect available models.")
app.add_typer(keys_app, name="keys")
app.add_typer(models_app, name="models")


# ---------------------------------------------------------------------------
# common options
# ---------------------------------------------------------------------------

TokenOpt = Annotated[
    str | None,
    typer.Option(
        "--token",
        envvar="ASKII_TOKEN",
        help="mPass OIDC JWT. Falls back to $ASKII_TOKEN.",
        show_envvar=True,
    ),
]
BaseUrlOpt = Annotated[
    str | None,
    typer.Option(
        "--base-url",
        envvar="ASKII_BASE_URL",
        help="Askii API base URL. Falls back to $ASKII_BASE_URL.",
        show_envvar=True,
    ),
]
OutputOpt = Annotated[
    OutputFmt,
    typer.Option(
        "--output",
        "-o",
        case_sensitive=False,
        help="Output format.",
    ),
]


def _build_client(token: str | None, base_url: str | None) -> Askii:
    if not token:
        stderr.print("[red]No token provided. Pass --token or set $ASKII_TOKEN.[/red]")
        raise typer.Exit(code=EXIT_AUTH)
    overrides: dict[str, Any] = {"token": token}
    if base_url:
        overrides["base_url"] = base_url
    return Askii(config=AskiiConfig.from_env(**overrides))


def _to_dict(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _render(value: Any, output: OutputFmt, *, table: Table | None = None) -> None:
    if output is OutputFmt.JSON:
        stdout.print_json(json.dumps(_to_dict(value), default=str))
        return
    if table is not None:
        stdout.print(table)
        return
    stdout.print_json(json.dumps(_to_dict(value), default=str))


def _handle(func: Any) -> Any:
    """Decorator: translate askii exceptions into stable exit codes."""
    import functools

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except AskiiAuthError as exc:
            stderr.print(f"[red]Authentication failed:[/red] {exc}")
            raise typer.Exit(code=EXIT_AUTH) from exc
        except AskiiValidationError as exc:
            stderr.print(f"[red]Validation error:[/red] {exc}")
            for fe in exc.field_errors:
                stderr.print(f"  - {fe.path}: {fe.msg} ({fe.type})")
            raise typer.Exit(code=EXIT_VALIDATION) from exc
        except AskiiServerError as exc:
            stderr.print(f"[red]Server error:[/red] {exc}")
            raise typer.Exit(code=EXIT_SERVER) from exc
        except AskiiTransportError as exc:
            stderr.print(f"[red]Transport error:[/red] {exc}")
            raise typer.Exit(code=EXIT_TRANSPORT) from exc
        except AskiiAPIError as exc:
            stderr.print(f"[red]API error:[/red] {exc}")
            raise typer.Exit(code=EXIT_API) from exc
        except AskiiError as exc:
            stderr.print(f"[red]Askii error:[/red] {exc}")
            raise typer.Exit(code=EXIT_UNEXPECTED) from exc

    return wrapper


# ---------------------------------------------------------------------------
# keys subcommands
# ---------------------------------------------------------------------------


@keys_app.command("list")
@_handle
def keys_list(
    token: TokenOpt = None,
    base_url: BaseUrlOpt = None,
    output: OutputOpt = OutputFmt.TABLE,
) -> None:
    """List active virtual keys for the authenticated user."""
    with _build_client(token, base_url) as client:
        resp = client.keys.list()
    if output is OutputFmt.TABLE:
        table = Table(title=f"Keys for {resp.user_id}")
        table.add_column("Name")
        table.add_column("Alias")
        table.add_column("Default model")
        table.add_column("Spend", justify="right")
        table.add_column("Expires")
        table.add_column("Memory")
        for k in resp.keys:
            table.add_row(
                k.key_name,
                k.key_alias or "—",
                k.default_model or "—",
                f"{k.spend:.4f}",
                k.expires.isoformat() if k.expires else "—",
                (k.memory_mode.value if k.memory_mode else ("on" if k.memory_enabled else "off")),
            )
        _render(resp, output, table=table)
    else:
        _render(resp, output)


@keys_app.command("provision")
@_handle
def keys_provision(
    token: TokenOpt = None,
    base_url: BaseUrlOpt = None,
    alias: Annotated[str | None, typer.Option("--alias", help="Human-readable key alias.")] = None,
    duration_days: Annotated[int, typer.Option("--duration-days", min=1, max=365)] = 90,
    memory_enabled: Annotated[bool, typer.Option("--memory/--no-memory")] = False,
    memory_mode: Annotated[MemoryMode | None, typer.Option("--memory-mode", case_sensitive=False)] = None,
    models: Annotated[
        list[str] | None,
        typer.Option("--model", "-m", help="Allowed model (repeatable). Empty = all."),
    ] = None,
    default_model: Annotated[str | None, typer.Option("--default-model")] = None,
    output: OutputOpt = OutputFmt.JSON,
) -> None:
    """Provision a new LiteLLM virtual key."""
    with _build_client(token, base_url) as client:
        resp = client.keys.provision(
            key_alias=alias,
            duration_days=duration_days,
            memory_enabled=memory_enabled,
            memory_mode=memory_mode,
            models=models,
            default_model=default_model,
        )
    # SecretStr renders as "**********" in dump unless we unwrap.
    payload = resp.model_dump(mode="json")
    payload["api_key"] = resp.api_key.get_secret_value()
    if output is OutputFmt.TABLE:
        table = Table(title="Provisioned key")
        for label, value in (
            ("api_key", payload["api_key"]),
            ("key_name", payload["key_name"]),
            ("user_id", payload["user_id"]),
            ("expires", payload.get("expires") or "—"),
        ):
            table.add_row(label, str(value))
        stdout.print(table)
        return
    stdout.print_json(json.dumps(payload, default=str))


@keys_app.command("revoke")
@_handle
def keys_revoke(
    token: TokenOpt = None,
    base_url: BaseUrlOpt = None,
    key: Annotated[str, typer.Option("--key", help="sk-... value or alias.")] = ...,  # type: ignore[assignment]
    output: OutputOpt = OutputFmt.JSON,
) -> None:
    """Revoke a key by sk-... value or alias."""
    with _build_client(token, base_url) as client:
        resp = client.keys.revoke(key=key)
    _render(resp, output)


@keys_app.command("get-config")
@_handle
def keys_get_config(
    token: TokenOpt = None,
    base_url: BaseUrlOpt = None,
    key: Annotated[str, typer.Option("--key")] = ...,  # type: ignore[assignment]
    output: OutputOpt = OutputFmt.JSON,
) -> None:
    """Print the model config for one key."""
    with _build_client(token, base_url) as client:
        resp = client.keys.get_config(key=key)
    _render(resp, output)


@keys_app.command("update-model")
@_handle
def keys_update_model(
    token: TokenOpt = None,
    base_url: BaseUrlOpt = None,
    key: Annotated[str, typer.Option("--key")] = ...,  # type: ignore[assignment]
    models: Annotated[list[str], typer.Option("--model", "-m", help="Allowed model (repeatable).")] = ...,  # type: ignore[assignment]
    default_model: Annotated[str | None, typer.Option("--default-model")] = None,
    output: OutputOpt = OutputFmt.JSON,
) -> None:
    """Update model config for a key."""
    with _build_client(token, base_url) as client:
        resp = client.keys.update_model(
            key=key,
            models=models,
            default_model=default_model,
        )
    _render(resp, output)


# ---------------------------------------------------------------------------
# models subcommands
# ---------------------------------------------------------------------------


@models_app.command("list")
@_handle
def models_list(
    token: TokenOpt = None,
    base_url: BaseUrlOpt = None,
    output: OutputOpt = OutputFmt.TABLE,
) -> None:
    """List models available on the platform."""
    with _build_client(token, base_url) as client:
        resp = client.models.list()
    if output is OutputFmt.TABLE:
        table = Table(title="Available models")
        table.add_column("Model")
        for m in resp.models:
            table.add_row(m.model_name)
        _render(resp, output, table=table)
    else:
        _render(resp, output)


# ---------------------------------------------------------------------------
# misc
# ---------------------------------------------------------------------------


@app.command("version")
def version() -> None:
    """Print the askii client version."""
    stdout.print(__version__)


def main() -> None:
    """Console-script entry point."""
    try:
        app()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover — defensive last resort
        stderr.print(f"[red]Unexpected error:[/red] {exc}")
        sys.exit(EXIT_UNEXPECTED)


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = ["app", "main", "OutputFmt"]
