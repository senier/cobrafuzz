# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Support code coverage and fuzzing at the same time

### Changed

- Make crash dir configurable (#13)

## [1.0.12] - 2024-01-24

### Added

- Mark package as py.typed (#9)

## [1.0.11] - 2024-01-18

### Changed

- Migrate to pytest
- Upgrade dependencies
- Introduce checks (ruff, black, kacl)
- Introduce type hints and mypy checks
- Rename to cobrafuzz
- Enable GitHub CI

[Unreleased]: https://github.com/senier/cobrafuzz/compare/v1.0.12...HEAD
[1.0.12]: https://github.com/senier/cobrafuzz/compare/v1.0.11...v1.0.12
[1.0.11]: https://github.com/senier/cobrafuzz/compare/1.0.10...v1.0.11
