# Changelog

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
