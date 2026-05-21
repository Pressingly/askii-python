# askii — Python client for the Askii platform API

A production-grade Python SDK for [`api.askii.ai`](https://api.askii.ai/docs/),
intended to be the single point of contact between Pressingly's FOSS apps
(SurfSense, Plane, Outline, Penpot, …) and the Askii platform.

* **Sync + async** — `Askii` and `AsyncAskii` siblings, same surface.
* **Resource-oriented** — `client.keys.list()`, `client.models.list()`, etc.,
  plus a low-level `client.request()` escape hatch for unwrapped endpoints.
* **Typed end-to-end** — Pydantic v2 models, `mypy --strict` in CI, `py.typed`
  ships in the wheel.
* **Production stack** — pluggable cache, tenacity retries with jitter,
  rich exception hierarchy, opt-in JSON logging with secret redaction,
  Prometheus/Datadog-friendly lifecycle hooks.
* **CLI included** — `askii keys list`, `askii keys provision …`, etc.

---

## Install

Pin against a tag in your consumer's `pyproject.toml`:

```toml
[project]
dependencies = [
    "askii @ git+https://github.com/Pressingly/askii-python.git@v0.1.0",
]
```

Or, with the optional Redis cache:

```toml
"askii[redis] @ git+https://github.com/Pressingly/askii-python.git@v0.1.0",
```

`uv` and `pip` both honor git URL specifiers.

---

## Quickstart

### Async (FastAPI, FastMCP, surfsense_backend, …)

```python
from askii import AsyncAskii

async with AsyncAskii(token=mpass_jwt) as client:
    keys = await client.keys.list()
    for k in keys.keys:
        print(k.key_name, k.spend, k.default_model)

    new = await client.keys.provision(key_alias="surfsense", duration_days=30)
    print(new.api_key.get_secret_value())  # unwrap SecretStr

    available = await client.models.list(cache_ttl=300)  # opt-in cache
```

### Sync (Django, scripts, ops tools)

```python
from askii import Askii

with Askii(token=mpass_jwt) as client:
    cfg = client.keys.get_config(key="surfsense")
    client.keys.update_model(key="surfsense", models=["gpt-4o", "claude-sonnet-4"])
```

### Low-level escape hatch — endpoints not yet wrapped

```python
raw: dict = await client.request(
    "POST",
    "/platform/some-future-endpoint",
    body={"foo": "bar"},
)
```

`mpass_token` is injected for you on every request.

---

## Authentication (passthrough)

The library does **not** acquire Cognito tokens itself. You pass a fresh
mPass JWT in one of three shapes:

```python
Askii(token="ey...")                        # static string
Askii(token=lambda: load_token())           # sync callable, called per request
AsyncAskii(token=async_token_provider)      # async callable / coroutine factory
```

The callable forms let you plug in refresh logic, AWS SSM lookups, or whatever
your auth flow needs.

Sync `Askii` rejects coroutine factories at construction with `AskiiAuthError`
— use `AsyncAskii` if you need async resolution.

---

## Configuration

```python
from askii import AskiiConfig, Hooks, AsyncAskii

cfg = AskiiConfig.from_env(
    base_url="https://api.askii.ai",   # or $ASKII_BASE_URL
    timeout=30.0,                      # or $ASKII_TIMEOUT_SECONDS
    max_retries=3,                     # or $ASKII_MAX_RETRIES
    http2=True,
    hooks=Hooks(...),                  # see below
)
client = AsyncAskii(token=jwt, config=cfg)
```

Recognized environment variables:

| Variable | Maps to | Default |
|---|---|---|
| `ASKII_BASE_URL` | `base_url` | `https://api.askii.ai` |
| `ASKII_TOKEN` | `token` | — |
| `ASKII_TIMEOUT_SECONDS` | `timeout` | `30.0` |
| `ASKII_MAX_RETRIES` | `max_retries` | `3` |

---

## Caching (off by default)

Cache is **off by default** to avoid surprise stale reads. Opt in per call:

```python
keys = await client.keys.list(cache_ttl=60)              # 1-minute cache
cfg  = await client.keys.get_config(key="x", cache_ttl=30)
mdls = await client.models.list(cache_ttl=300)           # 5-minute cache
```

Mutating calls (`provision`, `revoke`, `update_model`) invalidate the
relevant resource's cache automatically.

### Pluggable backends

```python
from askii import AskiiConfig, InMemoryCache
from askii._cache.redis import RedisCache                # requires [redis] extra

# In-process default
cfg = AskiiConfig(cache=InMemoryCache(maxsize=2048))

# Shared Redis (across processes / services)
cfg = AskiiConfig(cache=RedisCache(url="redis://valkey:6379/12", namespace="askii"))
```

Cache keys are per-user (derived from a SHA-256 hash of the resolved token —
**never the token itself**), so a shared `RedisCache` is safe across tenants.

You can also implement the `Cache` Protocol against any backend you like; it
covers both sync and async paths.

---

## Errors

```text
AskiiError
├── AskiiTransportError
│   ├── AskiiConnectionError
│   └── AskiiTimeoutError
└── AskiiAPIError(status, detail, request_id, response)
    ├── AskiiAuthError              # 401, 403
    ├── AskiiNotFoundError          # 404
    ├── AskiiValidationError        # 422 — field_errors: list[FieldError]
    ├── AskiiRateLimitError         # 429 — retry_after (s) when present
    └── AskiiServerError            # 5xx
```

422 responses are parsed into typed `FieldError(loc, msg, type)` entries so
callers can produce structured error messages:

```python
try:
    await client.keys.provision(duration_days=999)
except AskiiValidationError as exc:
    for fe in exc.field_errors:
        log.warning("%s: %s", fe.path, fe.msg)  # body.duration_days: out of range
```

5xx / 429 / connection / timeout errors are retried by the built-in tenacity
policy (max 3 attempts, exponential backoff with jitter, honors `Retry-After`).
4xx errors are not retried.

---

## Hooks and metrics

```python
from askii import Hooks, RequestEvent, ResponseEvent

def record_request(e: RequestEvent) -> None:
    metrics.counter("askii.requests").inc(method=e.method, path=e.path)

def record_response(e: ResponseEvent) -> None:
    metrics.histogram("askii.latency_ms").observe(e.elapsed_ms, status=e.status_code)

hooks = Hooks(
    on_request=record_request,
    on_response=record_response,
    on_retry=lambda e: log.warning("askii retry %d after %.2fs", e.attempt, e.sleep_seconds),
)
client = AsyncAskii(token=jwt, config=AskiiConfig(hooks=hooks))
```

Callback exceptions are caught and logged at WARNING — they never break the
underlying call.

---

## Logging (opt-in)

The library never force-configures Python logging. Inherits whatever the
consumer has set up. If you want askii's JSON formatter with secret redaction
and correlation-ID propagation:

```python
import askii

askii.configure_logging(level="INFO", json=True)
```

Redaction masks `mpass_token`, `api_key`, `Authorization`, `sk-…`, and JWT
patterns in both log messages and `extra={}` fields.

Bind a correlation ID across an async flow:

```python
from askii import bind_correlation_id, reset_correlation_id

token = bind_correlation_id("request-123")
try:
    await client.keys.list()
finally:
    reset_correlation_id(token)
```

The correlation ID is added to every log record and propagated to the upstream
as `X-Correlation-ID`.

---

## CLI

```bash
askii keys list
askii keys provision --alias surfsense --duration-days 30 -m gpt-4o
askii keys revoke --key surfsense
askii keys get-config --key surfsense
askii keys update-model --key surfsense -m gpt-4o -m claude-sonnet-4 --default-model gpt-4o
askii models list
askii version
```

* Token comes from `--token` or `$ASKII_TOKEN`.
* Base URL comes from `--base-url` or `$ASKII_BASE_URL`.
* Output: `--output table` (default for `list`) or `--output json`.

Exit codes: `0` ok · `2` auth · `3` validation · `4` transport · `5` server ·
`6` other API · `99` unexpected.

---

## Development

```bash
git clone https://github.com/Pressingly/askii-python
cd askii-python
uv venv
uv sync --extra dev --extra redis
uv run pre-commit install

uv run ruff check . && uv run ruff format --check .
uv run mypy --strict src/askii
uv run pytest --cov=askii --cov-fail-under=90 -v
uv build
```

See `CONTRIBUTING.md` for the contribution loop and `SECURITY.md` for
vulnerability reporting.

---

## License

MIT — see [LICENSE](./LICENSE).
