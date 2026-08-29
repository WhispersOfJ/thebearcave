# Changelog

## [1.15.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.14.0...v1.15.0) (2026-08-29)


### Features

* add MCP baseline comparison and refresh workflow ([a261051](https://github.com/WhispersOfJ/thebearcave/commit/a261051de05277818e595a933d9805aacc9216b6))


### Bug Fixes

* rename ambiguous loop variable to pass ruff E741 ([f130332](https://github.com/WhispersOfJ/thebearcave/commit/f1303327ef9b43a17efb17d1b6e66f54aa8f1d11))

## [1.14.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.13.0...v1.14.0) (2026-08-29)


### Features

* add Traefik dashboard link to landing page ([ffb56ac](https://github.com/WhispersOfJ/thebearcave/commit/ffb56ac4537f0dd46e62ec17ca80b86ea2740f43))
* deploy 9 new stack services with crowdsec bouncer and nzbdav categories ([3d25969](https://github.com/WhispersOfJ/thebearcave/commit/3d2596909c1daa7051bbca99e7c920d40cf7c3e2))
* switch landing page dashboard links to HTTPS nip.io hostnames ([69b18b7](https://github.com/WhispersOfJ/thebearcave/commit/69b18b78c2daba25b101e03bd722d299532e3ad7))
* update landing page with new services, health probes, and links ([b2bc2a8](https://github.com/WhispersOfJ/thebearcave/commit/b2bc2a8651692002261854b442856a60889d9cd9))


### Bug Fixes

* add missing ADGUARD_ADMIN_* vars to .env.template ([64ec98c](https://github.com/WhispersOfJ/thebearcave/commit/64ec98c764bbddf7544175734747128d1cdcc617))
* keep digests in trivy image extraction and re-key baseline to pins ([d06c333](https://github.com/WhispersOfJ/thebearcave/commit/d06c3338017600d91f0bd2dc9d455331276cc1db))
* sync update-nzbdav.sh dependents with compose cascade ([293523e](https://github.com/WhispersOfJ/thebearcave/commit/293523e747e3ced9b9580cba9717f4dbcdbf2f44))

## [1.13.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.12.1...v1.13.0) (2026-08-29)


### Features

* add audiobook and comic servers ([2d21c89](https://github.com/WhispersOfJ/thebearcave/commit/2d21c89612aab27c76481a201407c9d80dc71513))
* add Bazarr subtitle service ([8be99d4](https://github.com/WhispersOfJ/thebearcave/commit/8be99d44aa3b965b90fd7113ba6d52c9e774348f))
* add Lidarr and Readarr services ([871643c](https://github.com/WhispersOfJ/thebearcave/commit/871643c45122341946682a1f909fc13fed556fc6))
* add network security services ([879282a](https://github.com/WhispersOfJ/thebearcave/commit/879282a272c2ea4a2776e5a39ff23bc635c4b20f))
* add Vaultwarden and n8n services ([4e6f494](https://github.com/WhispersOfJ/thebearcave/commit/4e6f494a3f0fcf42d394522901bd643e25c4a096))


### Bug Fixes

* sync secret manifest with workflow usage ([1aeda7f](https://github.com/WhispersOfJ/thebearcave/commit/1aeda7fcc950dcb6debe52807a2c7bdc7bb1085d))

## [1.12.1](https://github.com/WhispersOfJ/thebearcave/compare/v1.12.0...v1.12.1) (2026-08-28)


### Bug Fixes

* **compose:** read node-exporter healthcheck body to stop log flood ([e4ed066](https://github.com/WhispersOfJ/thebearcave/commit/e4ed066271a9052ae2d2efa543769e94e5f7d7fc))
* **security:** eliminate 15 CRITICAL CVEs across the stack ([db5c97b](https://github.com/WhispersOfJ/thebearcave/commit/db5c97bca3a278b8e709d3e02f10a6abadf4340f))

## [1.12.0](https://github.com/WhispersOfJ/thebearcave/compare/v1.11.0...v1.12.0) (2026-08-28)


### Features

* **fish:** add generated tab completions for all stack-* commands ([9a3c154](https://github.com/WhispersOfJ/thebearcave/commit/9a3c1544bc14748f36df6d331f32087a674515b4))


### Bug Fixes

* **fish:** drop stray bash-style do; repair stack-help description matching ([a776913](https://github.com/WhispersOfJ/thebearcave/commit/a776913e47e05edcfd60e7c8c9784f015911b90f))
* **fish:** remediate systemic breakage across all stack-* functions ([8689b62](https://github.com/WhispersOfJ/thebearcave/commit/8689b62878dc0555cb9df6a18989f05ceb2bcf12))

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
