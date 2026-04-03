# Daemon Control CLI (`host.clients.ctl`)

This CLI controls boards through the running daemon HTTP API.

## Run

```bash
python -m host.clients.ctl --daemon-url http://127.0.0.1:8765 <command>
```

Default daemon URL is `http://127.0.0.1:8765`.

## Command tree

```text
health
transports
boards list
boards connect --board-id <id> --transport <label> [--transport-arg KEY VALUE]...
boards disconnect --board-id <id>
board <board_id> status
board <board_id> sensors
board <board_id> read --sensor <runtime_id>
board <board_id> set-period --sensor <runtime_id> --period-ms <ms>
board <board_id> get-period --sensor <runtime_id>
board <board_id> start --sensor <runtime_id>
board <board_id> stop --sensor <runtime_id>
board <board_id> stream --sensor <runtime_id> [--duration 5] [--poll-ms 250]
board <board_id> uptime
```

`board ... stream` is part of this daemon CLI (`host.clients.ctl`).
It is different from legacy direct stream in `host.cli stream`.

## Typical workflow

1. Ensure daemon is running:

```bash
python -m host.daemon --host 127.0.0.1 --port 8765
```

2. Discover transports:

```bash
python -m host.clients.ctl transports
```

3. Connect a board:

```bash
python -m host.clients.ctl boards connect --board-id sim1 --transport tcp --transport-arg ip 127.0.0.1 --transport-arg port 9000
```

4. Inspect and operate:

```bash
python -m host.clients.ctl board sim1 sensors
python -m host.clients.ctl board sim1 read --sensor 1
python -m host.clients.ctl board sim1 set-period --sensor 1 --period-ms 1000
python -m host.clients.ctl board sim1 start --sensor 1
python -m host.clients.ctl board sim1 stream --sensor 1 --duration 5 --poll-ms 250
python -m host.clients.ctl board sim1 stop --sensor 1
```

5. Disconnect when done:

```bash
python -m host.clients.ctl boards disconnect --board-id sim1
```

## Notes

- `--transport` expects the transport label defined in metadata (for example `uart`, `tcp`).
- `--transport-arg KEY VALUE` can be passed multiple times.
- `set-period` accepts only allowed period presets configured in the host app.
- `board ... stream` starts stream via daemon API, polls drained readings, then stops stream in cleanup.
