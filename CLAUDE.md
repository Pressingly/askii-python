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
├── _endpoints.py          # centralized "/platform/..." path constants
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
│   ├── keys.py            # KeysResource / AsyncKeysResource — 5 Platform Key Management endpoints
│   └── models.py          # ModelsResource / AsyncModelsResource — available-models
├── models/                # Pydantic v2 request + response pairs per endpoint
└── cli/_app.py            # typer-based `askii` CLI
```

## Design rules

* **Passthrough auth.** The library does not acquire Cognito tokens. Callers
  pass an mPass JWT (str, sync callable, or async callable). Tokens are
  resolved per request.
* **`mpass_token` always wins over caller body.** Client `_arequest` /
  `_request` merge in the order `{**body, "mpass_token": token}` so a buggy
  or malicious caller passing `body={"mpass_token": ...}` can't shadow the
  resolver. There is a regression test in `test_clients.py` — don't flip the
  merge order back.
* **URL paths live in `_endpoints.py`.** Every resource method imports its
  path from there (`PROVISION_KEY`, `LIST_KEYS`, etc.). Never hardcode a
  `"/platform/..."` literal at a call site — a typo becomes a silent 404.
  Tests pin against the same constants. The escape-hatch `client.request()`
  is the one place raw strings are intentional.
* **Sync + async siblings.** `Askii` and `AsyncAskii` share the same transport
  engine via `HTTPTransport(sync=True|False)`. Both classes mirror each other's
  surface.
* **Resource-oriented + escape hatch.** New endpoints get a resource method;
  ad-hoc calls go through `client.request(method, path, body=…)` which still
  injects `mpass_token` and accepts an `idempotent=…` flag.
* **`idempotent=False` for mutating POSTs.** Retrying a non-idempotent POST
  is unsafe (a 5xx may mean the upstream did execute the mutation but failed
  to respond). `keys.provision`, `keys.revoke`, `keys.update_model` pass
  `idempotent=False` to skip the retry policy; read-only ops keep the default
  `True`. When wrapping a new mutating endpoint, set `idempotent=False`.
* **Cache off by default.** `AskiiConfig` ships an `InMemoryCache(default_ttl=0)`
  so no implicit caching happens. Callers opt in per call via `cache_ttl=…`.
  Cache keys hash the token (per-user namespacing); the raw token never appears
  in a key.
* **Strict typing.** `mypy --strict` in CI, `py.typed` in the wheel,
  `extra="forbid"` on every Pydantic model so upstream schema drift surfaces
  as test failures, not silent breakage.
* **Logging never force-configured.** The library uses `logging.getLogger("askii")`
  and inherits consumer config. `configure_logging()` is opt-in.
* **`Retry-After` accepts both forms.** RFC 7231 §7.1.3 allows delta-seconds
  *or* HTTP-date. `_parse_retry_after` handles both; don't shortcut back to
  seconds-only parsing.

## Configuration

`AskiiConfig.from_env()` reads:

| Env var | Mapped to | Notes |
|---|---|---|
| `ASKII_BASE_URL` | `base_url` | Defaults to `https://api.askii.ai` |
| `ASKII_TOKEN` | `token` | Static-string source for the resolver |
| `ASKII_TIMEOUT_SECONDS` | `timeout` | float |
| `ASKII_MAX_RETRIES` | `max_retries` | int |
| `ASKII_CA_BUNDLE` | `verify` (path) | Wins over `ASKII_VERIFY` if both set |
| `ASKII_VERIFY` | `verify` (`0/false/no/off` → False) | For local mkcert / dev only |

## When extending

### Adding a new endpoint

1. Add the path constant to `src/askii/_endpoints.py` and its `__all__`.
2. Add Pydantic request + response models under `src/askii/models/<resource>.py`.
3. Add resource methods to `resources/<resource>.py` (both async and sync).
   Import the path from `_endpoints`. Pass `idempotent=False` if it mutates.
4. Wire cache key + TTL (or skip caching) and invalidation if it's a mutation.
5. Re-export from `models/__init__.py` and `src/askii/__init__.py`.
6. Add unit tests: model round-trip, resource method (sync + async), and an
   update to `tests/unit/test_endpoints.py` if you've added a constant.
7. Add a CLI command if it's user-facing.
8. Update `CHANGELOG.md` under `## [Unreleased]`.

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

All four must pass before opening a PR. Today's baseline: 177 tests pass,
coverage ≥ 90%. CI matrix covers Python 3.10 → 3.14 × Ubuntu / macOS.

## Things to avoid

* Don't add new transitive deps without weighing against `pip install askii`'s
  install-time cost. We're consumed by multiple Django/FastAPI services.
* Don't add new top-level modules; keep internal helpers under `_*` so the
  public surface stays the explicit re-exports in `__init__.py`.
* Don't hardcode `"/platform/..."` URLs at call sites — use the constants in
  `_endpoints.py`.
* Don't widen `extra="forbid"` to `"allow"` on response models — the strict
  setting is the early-warning for upstream schema drift.
* Don't add `from askii._cache.redis import RedisCache` to the public
  `__init__.py`; keep it opt-in so consumers without the extra don't accidentally
  trigger the runtime import error.
* Don't print or log tokens directly. The redaction filter catches most cases,
  but the right pattern is `SecretStr` on response models and never logging the
  raw resolved token.
* Don't change the `{**body, "mpass_token": token}` merge order without thinking
  about the shadow-attack regression test.
* Don't retry mutating POSTs. New mutating endpoints must pass `idempotent=False`
  to the transport; new escape-hatch calls that mutate should pass the same.

## Reference

* Plan that bootstrapped this repo: see the original implementation plan (kept
  with the initial commit history).
* Upstream API docs: https://api.askii.ai/docs/
