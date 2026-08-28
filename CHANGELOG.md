# Changelog

## [1.11.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.10.1...v1.11.0) (2026-08-28)


### Features

* **nzbdav:** track InfiniDysk dev tag and add queue-guarded update script ([23a4e2a](https://github.com/WhispersOfJ/thebearcave/commit/23a4e2a003db6e0aa6383049366f31bacc2bab43))
* **plex:** use official beta image ([e3323c3](https://github.com/WhispersOfJ/thebearcave/commit/e3323c310568315cacf3650588709beb1cf2d292))

## [1.10.1](https://github.com/WhispersOfJ/thebearcave/compare/v1.10.0...v1.10.1) (2026-08-27)


### Bug Fixes

* **landing-page:** correct Mermaid graph edge node IDs ([c8efb03](https://github.com/WhispersOfJ/thebearcave/commit/c8efb03f77227fdaa130df7bd6484fa22ea04438))
* **security:** revert wrong image pins, recreate containers with resource limits ([fae4f3c](https://github.com/WhispersOfJ/thebearcave/commit/fae4f3c677acb2547418a10d839545ab20627116))

## [1.10.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.9.1...v1.10.0) (2026-08-27)


### Features

* **monitoring:** add backup freshness, disk fill rate, and load alerts ([#39](https://github.com/WhispersOfJ/thebearcave/issues/39)) ([e5f924c](https://github.com/WhispersOfJ/thebearcave/commit/e5f924c9df00781b9cf00bd1edf7e5097e1cf27d))
* **security:** add resource limits to all 22 services ([#5](https://github.com/WhispersOfJ/thebearcave/issues/5)) ([fb3b43a](https://github.com/WhispersOfJ/thebearcave/commit/fb3b43a8ef32e3afff70c6d549a6fc39891b9fed))


### Bug Fixes

* **alerts:** correct BackupStale metric and HostHighLoad PromQL ([39e7030](https://github.com/WhispersOfJ/thebearcave/commit/39e703099437b9d3d3bf5370e8caab0490f9e44b))

## [1.9.1](https://github.com/WhispersOfJ/thebearcave/compare/v1.9.0...v1.9.1) (2026-08-27)


### Bug Fixes

* **ci:** add actionlint checksum verification + pre-commit gate + docs ([aebec8d](https://github.com/WhispersOfJ/thebearcave/commit/aebec8de2278e8fe50d3eb9ed9b8133397acb8d8))
* **ci:** add pytest to exporter test dependencies ([16d1ab5](https://github.com/WhispersOfJ/thebearcave/commit/16d1ab53c0feb0f4eed51729961b75630686ad38))
* **ci:** correct actionlint SHA-256 checksum ([19d6fa9](https://github.com/WhispersOfJ/thebearcave/commit/19d6fa953b06ad3afa9a4ce655d556d4a7d459a5))
* **security:** harden stack per potential.md audit items ([4f4255c](https://github.com/WhispersOfJ/thebearcave/commit/4f4255c8baa1eaa6e2ff42ce7bfc6422ac4f487c))

## [1.9.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.8.0...v1.9.0) (2026-08-27)


### Features

* **fish:** Phase 2 — rewrite 71 fish functions to bypass control panel ([c4e12f1](https://github.com/WhispersOfJ/thebearcave/commit/c4e12f1f76c691b6382d98069d34b2a96cac8aa7))
* **landing:** Phase 3 — replace control-panel health with direct service probes ([3efae51](https://github.com/WhispersOfJ/thebearcave/commit/3efae5188a4b9ac551b7770fa5b940e275bffd3f))
* Phase 4 — remove control panel, archive to archive/control-panel/ ([faf4127](https://github.com/WhispersOfJ/thebearcave/commit/faf41274be6a30a610b1e812284fef526a16d338))


### Bug Fixes

* **ci:** add DISCORD_WEBHOOK_URL to secret manifest ([54dc06e](https://github.com/WhispersOfJ/thebearcave/commit/54dc06e46c8c99aaad48f1c683752e5daf788a75))
* **ci:** add missing step id and fix reclaim accumulation in disk-cleanup ([3798e6c](https://github.com/WhispersOfJ/thebearcave/commit/3798e6c57814240ccaf8452af4309e4a81c22e20))
* **ci:** correct step output references and unit parsing in new workflows ([b03c135](https://github.com/WhispersOfJ/thebearcave/commit/b03c135b8bdc22d7f1d43edb49900c3f553ea25e))
* **ci:** fix actionlint errors in cert-expiry-check, disk-cleanup, codeql ([f27e200](https://github.com/WhispersOfJ/thebearcave/commit/f27e200e684c785d04fd42859473a79e140fe1d0))
* **fish:** fix broken __stack_api calls after control panel removal ([79058dd](https://github.com/WhispersOfJ/thebearcave/commit/79058dd9fa335e675159d5fce7a6b5b453a33736))
* **fish:** implement all 17 custom integration functions + fix Plex health ([950f925](https://github.com/WhispersOfJ/thebearcave/commit/950f925d48c3c58154a87d03f4ae0b0226947c4c))
* **fish:** three bugs in Phase 1 direct-service routing ([37db0a8](https://github.com/WhispersOfJ/thebearcave/commit/37db0a89a23754c45e3cbfa13cd905471629761d))
* restore FRONTEND_BACKEND_API_KEY to .env.template ([2f8fabe](https://github.com/WhispersOfJ/thebearcave/commit/2f8fabe585a8ab0be2021d6fc42feae78ab50ed4))

## [1.8.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.7.0...v1.8.0) (2026-08-27)


### Features

* **fish:** Phase 1 — direct service API helpers, bypass control panel ([a78c8bf](https://github.com/WhispersOfJ/thebearcave/commit/a78c8bf0258b9777727d5a3c78ab123315e2cd1e))


### Bug Fixes

* **helper:** fix image/command order, input validation, error handling ([aef7108](https://github.com/WhispersOfJ/thebearcave/commit/aef71084143fb9c824d32bba31fda73daa3ddc9a))
* **security:** remove writable Docker socket from control-panel (item [#1](https://github.com/WhispersOfJ/thebearcave/issues/1)) ([4fe6321](https://github.com/WhispersOfJ/thebearcave/commit/4fe6321f1766d5d811ed65d0eae2fd65a34ccd83))

## [1.7.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.6.0...v1.7.0) (2026-08-27)


### Features

* **security:** harden control panel + fix no-op Trivy gate ([44f97ae](https://github.com/WhispersOfJ/thebearcave/commit/44f97ae17e936bd12c58b1a9aea1e790d293d4c2))

## [1.6.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.5.0...v1.6.0) (2026-08-27)


### Features

* Alertmanager with Discord notifications + Cleanuparr setup docs ([18861dc](https://github.com/WhispersOfJ/thebearcave/commit/18861dcd321cf5956908b8bce84c5328378eb419))
* **cli:** add /api/v2/cli/ endpoints for fish functions ([32f475c](https://github.com/WhispersOfJ/thebearcave/commit/32f475c04655daff966bbd2d9904673c6d8ba1a7))
* **fish:** complete rewrite of all fish functions — 95 API-backed + 23 host tools ([979d769](https://github.com/WhispersOfJ/thebearcave/commit/979d76935df5b9429476d7250145237fc03dac25))
* monitoring stack — Grafana dashboards, Prometheus alert rules, landing page integration test ([edb6c5c](https://github.com/WhispersOfJ/thebearcave/commit/edb6c5ca418a9d2f669577481b8cf097cb845be8))
* **security:** add login rate limiting and failed-attempt logging ([523d840](https://github.com/WhispersOfJ/thebearcave/commit/523d84087a9cec78bc9c51e626925efe5e7f7465))


### Bug Fixes

* **catalog:** change network constant from 'stacknet' to 'bearcave' ([d16248e](https://github.com/WhispersOfJ/thebearcave/commit/d16248e50364f8cf6f9f6ab1367db558f621d549))
* **test:** use temp file to avoid pipefail issue with large HTML pages ([94defd8](https://github.com/WhispersOfJ/thebearcave/commit/94defd8ace62ec3c79a4a3d517307b974b29bd73))


### Performance Improvements

* gzip compression + lazy-load Mermaid for landing page ([ea70f4d](https://github.com/WhispersOfJ/thebearcave/commit/ea70f4d57ad1b2d72d3b3045c7e7d1d494b1e015))

## [1.5.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.4.1...v1.5.0) (2026-08-26)


### Features

* ecosystem improvements — full health coverage, live Mermaid colors, registry as single source ([346cd14](https://github.com/WhispersOfJ/thebearcave/commit/346cd144cfc70d5fb08169e5500120ed8a1b4a2c))

## [1.4.1](https://github.com/WhispersOfJ/thebearcave/compare/v1.4.0...v1.4.1) (2026-08-26)


### Bug Fixes

* health view covers 19 services, backlinks use absolute URLs, registry validation, docstring accuracy ([6ab8e5c](https://github.com/WhispersOfJ/thebearcave/commit/6ab8e5c5cd88febea6d1242e51290757c1234095))
* **landing-page:** correct pipeline flow parallelism and guard Mermaid ([2753f11](https://github.com/WhispersOfJ/thebearcave/commit/2753f110d5da679d954ce0b4201f135488da85a3))

## [1.4.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.3.2...v1.4.0) (2026-08-26)


### Features

* unified ecosystem — service registry, category layout, Mermaid graph, detail panels, backlinks ([06889f5](https://github.com/WhispersOfJ/thebearcave/commit/06889f53265ed56d05f4b1b1c14a8256a7e396b5))

## [1.3.2](https://github.com/WhispersOfJ/thebearcave/compare/v1.3.1...v1.3.2) (2026-08-26)


### Bug Fixes

* **landing-page:** same-origin health fetch fixes HTTPS status dots ([46caf92](https://github.com/WhispersOfJ/thebearcave/commit/46caf92a05e22bb8119f2c33267017d7cb1fd6dc))

## [1.3.1](https://github.com/WhispersOfJ/thebearcave/compare/v1.3.0...v1.3.1) (2026-08-26)


### Bug Fixes

* **landing-page:** repoint doc links from media-stack to thebearcave ([ff5c3c5](https://github.com/WhispersOfJ/thebearcave/commit/ff5c3c56aa99b1134305bbf371a26d4236bd0e57))

## [1.3.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.2.0...v1.3.0) (2026-08-26)


### Features

* **landing-page:** CA-trust badge backed by the live TLS probe ([81d20b6](https://github.com/WhispersOfJ/thebearcave/commit/81d20b6433475795238ce060072b0f9a525fee3b))

## [1.2.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.1.0...v1.2.0) (2026-08-26)


### Features

* **control-panel:** read-only TLS cert diagnostic endpoint ([33de97e](https://github.com/WhispersOfJ/thebearcave/commit/33de97e60388e9cc077032b43150ac908f20abf6))
* **setup:** sync RELEASE_PLEASE_TOKEN to GitHub Actions secrets ([178d36a](https://github.com/WhispersOfJ/thebearcave/commit/178d36ad2ef7a984b5d6977ac126a5358c949704))

## [1.1.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.0.0...v1.1.0) (2026-08-26)


### Features

* Ansible playbook to auto-trust the local CA on LAN devices ([3b10053](https://github.com/WhispersOfJ/thebearcave/commit/3b10053d7b6e042bb09d2d8248c07afeba4feb00))
* certificate setup section on the landing page ([c78f7f6](https://github.com/WhispersOfJ/thebearcave/commit/c78f7f6e2dd37262e0968d0ee738c6b3bd7552e0))
* initial scaffold — merge media-stack + metacacharr into The Bear Cave ([a0c976d](https://github.com/WhispersOfJ/thebearcave/commit/a0c976de3b42f8d9f7ee257943e9bce55f5866ba))
* local CA (mkcert) with trusted wildcard cert for all nip.io hostnames ([736f8c3](https://github.com/WhispersOfJ/thebearcave/commit/736f8c357c399a1631626b5029d86ef17fad10b1))
* trust the local CA inside every stack container ([e2acbe0](https://github.com/WhispersOfJ/thebearcave/commit/e2acbe08342c0ead95a80c665098e1a95ba09516))


### Bug Fixes

* align docs and gitignore with config/ layout after Phase 4 migration ([85841e7](https://github.com/WhispersOfJ/thebearcave/commit/85841e7c2804fac09602c08a9f524da7704ddef3))
* allow docker type and drop invalid input in PR title lint ([7d889e1](https://github.com/WhispersOfJ/thebearcave/commit/7d889e1e63570105a4619ad51dbe96453224d7d0))
* fall back to GITHUB_TOKEN when release-please PAT is unset ([1952a08](https://github.com/WhispersOfJ/thebearcave/commit/1952a084695b63555e7f10b74bd10300fa8c9400))
* remove invalid size expression from PR labeler workflow ([6ab944b](https://github.com/WhispersOfJ/thebearcave/commit/6ab944b5446c8f056757bec84cf4228355606620))
* remove unused variables flagged by shellcheck in health checks ([623432b](https://github.com/WhispersOfJ/thebearcave/commit/623432b66f7d9484e405bcdbd9fa9d364d8ed0be))
* stop failed Let's Encrypt attempts on LAN stack ([ef2ab3c](https://github.com/WhispersOfJ/thebearcave/commit/ef2ab3c6a2da4c6e0f7226b4eca48a35bdf75c4d))
