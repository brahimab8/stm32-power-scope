# Testing Guide

This project has multiple test layers. Use the commands below depending on scope.

## Python host unit tests

Default test path is `host/tests`.

```bash
pytest host/tests -q
```

Includes protocol, runtime, app, transport, and daemon unit tests.

You can also force marker-based selection:

```bash
pytest -m unit host/tests -q
```

## Python integration tests

Integration tests live in `tests/integration` and are marked `integration`.

Run all integration tests:

```bash
pytest tests/integration -m integration -q
```

Run daemon/simulator integration test:

```bash
pytest tests/integration/test_daemon_sim_integration.py -q
```

## Python marker usage

Registered markers:

- `unit`: host-app unit tests in `host/tests`
- `integration`: cross-component tests (daemon + simulator + transport)

Examples:

```bash
pytest -m unit host/tests -q
pytest -m integration -q
```

## C core tests (Unity + CTest)

From repo root:

```bash
git submodule update --init
make build
make test
```

Optional coverage:

```bash
make coverage
```

## Simulator manual smoke test

1. Run simulator (`scripts/run-sim.ps1` on Windows).
2. Start daemon (`python -m host.daemon`).
3. Run a minimal control flow with `host.clients.ctl`:

```bash
python -m host.clients.ctl boards connect --board-id sim1 --transport tcp --transport-arg ip 127.0.0.1 --transport-arg port 9000
python -m host.clients.ctl board sim1 read --sensor 1
python -m host.clients.ctl boards disconnect --board-id sim1
```
