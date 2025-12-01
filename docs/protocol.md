# Protocol Definitions (V0)

This document describes the **wire protocol** used between the STM32 firmware and the host application.

The protocol is binary, transport-agnostic, and supports serialized command/response exchanges alongside continuous real-time sensor streaming.

The authoritative definitions live in the YAML files under `host/metadata/protocol/`.

---

## Overview

* **Encoding**: Binary, little-endian
* **Framing**: Fixed-size header + variable payload + CRC
* **Direction**:
  * Host → Device: commands (`CMD`)
  * Device → Host: streams (`STREAM`) and responses (`ACK` / `NACK`)

---

## Constants

Defined in
[`constants.yml`](../host/metadata/protocol/constants.yml)

| Name               | Value      | Description                  |
| ------------------ | ---------- | ---------------------------- |
| `magic`            | `0x5AA5`   | Frame synchronization marker |
| `protocol_version` | `0`        | Wire protocol version        |
| `hdr_len`          | `16` bytes | Header size                  |
| `crc_len`          | `2` bytes  | CRC length                   |
| `max_payload`      | `46` bytes | Maximum payload size         |
| `frame_max_bytes`  | `64` bytes | Header + payload + CRC       |

### CRC

* Algorithm: **CRC-16/CCITT-FALSE**
* Polynomial: `0x1021`
* Seed: `0xFFFF`

---

## Frame Format

Defined in
[`header.yml`](../host/metadata/protocol/header.yml)

Each frame starts with a 16-byte header, followed by an optional payload and CRC.
The maximum frame size is currently 64 bytes (header + payload + CRC).

### Header Layout

| Field    | Type     | Description               |
| -------- | -------- | ------------------------- |
| `magic`  | `uint16` | Protocol magic number     |
| `type`   | `uint8`  | Frame type                |
| `ver`    | `uint8`  | Protocol version          |
| `len`    | `uint16` | Payload length (bytes)    |
| `cmd_id` | `uint8`  | Command ID (for `CMD`)    |
| `rsv`    | `uint8`  | Reserved (0)              |
| `seq`    | `uint32` | Sequence / correlation ID |
| `ts_ms`  | `uint32` | Device timestamp (ms)     |

---

## Frame Types

Defined in [`frames.yml`](../host/metadata/protocol/frames.yml).

| Type     | Code | Direction     | Description         |
| -------- | ---- | ------------- | ------------------- |
| `STREAM` | `0`  | Device → Host | Sensor data stream  |
| `CMD`    | `1`  | Host → Device | Command request     |
| `ACK`    | `2`  | Device → Host | Successful response |
| `NACK`   | `3`  | Device → Host | Error response      |

### Notes

* `STREAM` payload begins with `runtime_id:uint8`; remaining bytes are sensor-specific (device: `powerscope/src/ps_sensor_*.c`, host: [`sensors.yml`](../host/metadata/sensors.yml)).

---

## Response semantics

Every `CMD` receives exactly one `ACK` or `NACK`.  

- `ACK` frames may include a payload. 
- `NACK` frames carry a single error-code byte.  

Responses echo the original `cmd_id` and `seq` fields to allow correlation with the command.

---

## Commands

Defined in [`commands.yml`](../host/metadata/protocol/commands.yml).

| Command        | ID     | CMD Payload                               | ACK Payload                                 | Description         |
| -------------- | ------ | ----------------------------------------- | ------------------------------------------- | ------------------- |
| `START_STREAM` | `0x01` | `sensor_id : uint8`                       | —                                           | Start streaming     |
| `STOP_STREAM`  | `0x02` | `sensor_id : uint8`                       | —                                           | Stop streaming      |
| `SET_PERIOD`   | `0x03` | `sensor_id : uint8`, `period_ms : uint16` | —                                           | Set stream period   |
| `GET_PERIOD`   | `0x04` | `sensor_id : uint8`                       | `period_ms : uint32`                        | Query stream period |
| `PING`         | `0x05` | —                                         | —                                           | Connectivity check  |
| `GET_SENSORS`  | `0x06` | —                                         | `[{ runtime_id:uint8, type_id:uint8 }, … ]` | Enumerate sensors   |

---

## Errors

Defined in
[`errors.yml`](../host/metadata/protocol/errors.yml)

Error codes are returned in `NACK` frames.

| Code  | Name            | Description                    |
| ----- | --------------- | ------------------------------ |
| `1`   | `INVALID_CMD`   | Unknown or unsupported command |
| `2`   | `INVALID_LEN`   | Invalid payload length         |
| `3`   | `INVALID_VALUE` | Invalid argument value         |
| `4`   | `SENSOR_BUSY`   | Sensor already streaming       |
| `5`   | `OVERFLOW`      | Internal buffer overflow       |
| `6`   | `INTERNAL`      | Internal error                 |
| `255` | `UNKNOWN`       | Unspecified error              |

---

## Versioning

* The protocol is currently **version 0**.
* Firmware and host must agree on the protocol version.

---

## Related Files

* Firmware protocol definitions:
  `powerscope/include/protocol_defs.h`
  `powerscope/include/ps_cmd_defs.h`
* Host protocol metadata (yml files):
  `host/metadata/protocol/`

---
