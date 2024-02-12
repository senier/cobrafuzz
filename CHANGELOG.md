# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.1] - 2024-02-12

### Added

- Saving fuzzer state to file (#15)
- Loading crash coverage from crash dir on startup (#25)

## [2.1.0] - 2024-02-10

### Added

- Python 3.8 support
- Support for "spawn" and "forkserver" start methods

### Fixed

- Potential deadlocks due to use of "fork" start method

### Removed

- Fixed artifact name (#27)


## [2.0.0] - 2024-02-05

### Added

- Parallel fuzzing (#11)
- Global timeout (#14)
- Support for code coverage and fuzzing at the same time

### Fixed

- Use cryptographic randomness (#16)
- Regression mode
- Prevent tracer from being replaced by secondary tracer

### Changed

- Continue after error was found, make number of errors configurable (#12)
- Make crash dir configurable (#13)
- Use mp.get_context for multiprocessing (#1)
- Report only crashes for new paths (#19)
- Use flags instead of file descriptor mask to close stdout and stderr
- Make logging frequency configurable via --stat-frequency

### Removed

- Memory limit checking
- Per-run timeout

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

[2.1.1]: https://github.com/senier/cobrafuzz/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/senier/cobrafuzz/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/senier/cobrafuzz/compare/v1.0.12...v2.0.0
[1.0.12]: https://github.com/senier/cobrafuzz/compare/v1.0.11...v1.0.12
[1.0.11]: https://github.com/senier/cobrafuzz/compare/1.0.10...v1.0.11
