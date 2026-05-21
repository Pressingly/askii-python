# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial release scaffolding for the Askii Python client.
- `Askii` (sync) and `AsyncAskii` (async) clients with shared transport.
- Resource-oriented API: `client.keys.*`, `client.models.*`, plus low-level `client.request()` escape hatch.
- Pydantic v2 request/response models; `SecretStr`-wrapped provisioned `api_key`.
- Typed exception hierarchy with `FieldError` mapping for 422 responses.
- Pluggable `Cache` Protocol with `InMemoryCache` and optional `RedisCache` (`[redis]` extra).
- tenacity-based retries with exponential backoff + jitter; honors `Retry-After`.
- Lifecycle hooks (`on_request`, `on_response`, `on_retry`, `on_cache_hit`, `on_cache_miss`, `on_error`).
- Opt-in JSON logging with secret redaction and correlation-ID propagation.
- Bundled `askii` CLI (typer + rich) covering all Platform Key Management endpoints.

[Unreleased]: https://github.com/Pressingly/askii-python/compare/v0.0.0...HEAD
