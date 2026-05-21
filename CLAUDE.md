# CLAUDE.md

Guidance for Claude Code (and other AI coding agents) when working in this repo.

## What this is

`askii-python` is the shared Python client for `https://api.askii.ai/`. It's
consumed by the Pressingly FOSS apps (SurfSense, Plane, …) and the MCP servers
that wrap them. It is intentionally the **only** place where askii HTTP details
live; consumers depend on `askii` and use its high-level resources.

## Architecture (one-line per file)

```
src/askii/
├── __init__.py            # public re-exports — keep this surface intentional
├── _config.py             # AskiiConfig frozen dataclass + from_env()
├── _transport.py          # HTTPTransport — sync + async, cache + retry + hooks
├── _retry.py              # tenacity policy (5xx / 429 / network), honors Retry-After
├── _hooks.py              # Hooks dataclass + RequestEvent/ResponseEvent/RetryEvent
├── _logging.py            # configure_logging(), redaction + correlation-ID filters
├── _errors.py             # exception hierarchy + map_response_to_error()
├── _token.py              # sync + async token resolvers (string / callable / coroutine)
├── _cache/
│   ├── __init__.py        # Cache Protocol + per-user cache-key builders
│   ├── memory.py          # InMemoryCache (TTL + LRU, dual sync/async locks)
│   └── redis.py           # RedisCache ([redis] extra; lazy redis import)
├── _client/
│   ├── async_client.py    # AsyncAskii (owns transport + resources)
│   └── sync_client.py     # Askii
├── resources/
│   ├── _base.py           # _AsyncResource / _SyncResource bases
│   ├── keys.py            # KeysResource / AsyncKeysResource — 5 of 6 endpoints
│   └── models.py          # ModelsResource / AsyncModelsResource — available-models
├── models/                # Pydantic v2 request + response pairs per endpoint
└── cli/_app.py            # typer-based `askii` CLI
```

## Design rules

* **Passthrough auth.** The library does not acquire Cognito tokens. Callers
  pass an mPass JWT (str, sync callable, or async callable). Tokens are
  resolved per request.
* **Sync + async siblings.** `Askii` and `AsyncAskii` share the same transport
  engine via `HTTPTransport(sync=True|False)`. Both classes mirror each other's
  surface.
* **Resource-oriented + escape hatch.** New endpoints get a resource method;
  ad-hoc calls go through `client.request(method, path, body=…)` which still
  injects `mpass_token`.
* **Cache off by default.** `AskiiConfig` ships an `InMemoryCache(default_ttl=0)`
  so no implicit caching happens. Callers opt in per call via `cache_ttl=…`.
  Cache keys hash the token (per-user namespacing); the raw token never appears
  in a key.
* **Strict typing.** `mypy --strict` in CI, `py.typed` in the wheel,
  `extra="forbid"` on every Pydantic model so upstream schema drift surfaces
  as test failures, not silent breakage.
* **Logging never force-configured.** The library uses `logging.getLogger("askii")`
  and inherits consumer config. `configure_logging()` is opt-in.

## When extending

### Adding a new endpoint

1. Add Pydantic request + response models under `src/askii/models/<resource>.py`.
2. Add resource methods to `resources/<resource>.py` (both async and sync).
3. Wire cache key + TTL (or skip caching) and invalidation if it's a mutation.
4. Re-export from `models/__init__.py` and `src/askii/__init__.py`.
5. Add a unit test for the model round-trip and the resource method (sync + async).
6. Add a CLI command if it's user-facing.
7. Update `CHANGELOG.md` under `## [Unreleased]`.

### Adding a new resource namespace

Mirror the `keys` / `models` resources. Each namespace gets a sync + async pair
with the same surface, and the parent client constructor instantiates both.

### Cache invalidation

After a mutating call:

```python
await self._client._ainvalidate(_RESOURCE)   # async resource
self._client._invalidate(_RESOURCE)          # sync resource
```

This deletes all cache entries under the current user's resource prefix.

## Local verification loop

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/askii
uv run pytest --cov=askii --cov-fail-under=90 -v
uv build
```

All four must pass before opening a PR.

## Things to avoid

* Don't add new transitive deps without weighing against `pip install askii`'s
  install-time cost. We're consumed by multiple Django/FastAPI services.
* Don't add new top-level modules; keep internal helpers under `_*` so the
  public surface stays the explicit re-exports in `__init__.py`.
* Don't widen `extra="forbid"` to `"allow"` on response models — the strict
  setting is the early-warning for upstream schema drift.
* Don't add `from askii._cache.redis import RedisCache` to the public
  `__init__.py`; keep it opt-in so consumers without the extra don't accidentally
  trigger the runtime import error.
* Don't print or log tokens directly. The redaction filter catches most cases,
  but the right pattern is `SecretStr` on response models and never logging the
  raw resolved token.

## Reference

* Plan that bootstrapped this repo: see the original implementation plan (kept
  with the initial commit history).
* Upstream API docs: https://api.askii.ai/docs/
