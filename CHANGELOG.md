# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No changes yet._

## [0.1.0] - 2026-05-21

### Added

- Initial release scaffolding for the Askii Python client.
- `Askii` (sync) and `AsyncAskii` (async) clients with shared transport.
- Resource-oriented API: `client.keys.*`, `client.models.*`, plus low-level `client.request()` escape hatch.
- Pydantic v2 request/response models; `SecretStr`-wrapped provisioned `api_key`.
- Typed exception hierarchy with `FieldError` mapping for 422 responses.
- Pluggable `Cache` Protocol with `InMemoryCache` and optional `RedisCache` (`[redis]` extra).
- tenacity-based retries with exponential backoff + jitter; honors `Retry-After` (now also accepts HTTP-date form).
- Per-call `idempotent` flag on `client.request()` / transport. Mutating resource methods (`keys.provision`, `keys.revoke`, `keys.update_model`) opt out of the retry policy so a transient 5xx cannot double-apply a mutation.
- Lifecycle hooks (`on_request`, `on_response`, `on_retry`, `on_cache_hit`, `on_cache_miss`, `on_error`).
- Opt-in JSON logging with secret redaction and correlation-ID propagation.
- Bundled `askii` CLI (typer + rich) covering all Platform Key Management endpoints.
- CI matrix now covers Python 3.10 through 3.14.
- `ASKII_VERIFY` and `ASKII_CA_BUNDLE` environment variables wire TLS verification into `AskiiConfig.from_env`.

### Changed

- Centralize Platform Key Management URL paths in `askii._endpoints` so upstream renames or version-prefix changes are a one-line edit.

### Fixed

- `mpass_token` injection now wins over any caller-supplied `mpass_token` in `body=…` (previously, a caller's key could shadow the resolver's token).
- `Retry-After` headers in HTTP-date form (RFC 7231 §7.1.3) are now parsed correctly; previously they fell back to exponential backoff and ignored the server's wait hint.

[Unreleased]: https://github.com/Pressingly/askii-python/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Pressingly/askii-python/releases/tag/v0.1.0
