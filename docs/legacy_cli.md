# Legacy Direct CLI (`host.cli`)

`host.cli` is the original direct CLI path (no daemon).
It talks directly to one transport endpoint per invocation.

## Status

- Kept for now for quick low-level workflows.
- Multi-board control workflows should use daemon + `host.clients.ctl`.

## Commands

```text
transports
status --transport <label> [transport args]
sensors --transport <label> [transport args] [--read <id> ...] [--record]
stream --transport <label> [transport args] [--sensor <id> ...] [--period-ms <ms>] [--secs <s>] [--record]
```

## Examples

TCP simulator:

```bash
python -m host.cli status --transport tcp --ip 127.0.0.1 --port 9000
python -m host.cli sensors --transport tcp --ip 127.0.0.1 --port 9000 --read 1
python -m host.cli stream --transport tcp --ip 127.0.0.1 --port 9000 --secs 10 --period-ms 1000 --record
```

UART board:

```bash
python -m host.cli status --transport uart --port COM4
```
