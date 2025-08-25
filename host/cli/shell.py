# shell.py
import argparse, time
from host.common.serial_link import open_port
from host.common.protocol import (
    read_frame, send_start, send_stop,
    PROTO_TYPE_STREAM, PROTO_TYPE_ACK, PROTO_TYPE_NACK,
)
from host.common.telemetry import decode_data_frame
from host.common.control import parse_control_frame, format_control_event


def main():
    ap = argparse.ArgumentParser(description="STM32 Power Scope shell (CDC streaming)")
    ap.add_argument('-p', '--port', help='Serial port (auto-detect if omitted)')
    ap.add_argument('--start', action='store_true', help='send START on open (once)')
    ap.add_argument('--stop',  action='store_true', help='send STOP on open (once)')
    args = ap.parse_args()

    ser = open_port(args.port)  # asserts DTR by default
    print(f'Opened {ser.port} (DTR={"on" if ser.dtr else "off"})')

    if args.stop:
        send_stop(ser, wait_reply=False)
    if args.start:
        send_start(ser, wait_reply=False)

    print('Listening… Ctrl+C to quit')
    last_seq = None
    frames = 0
    t0 = time.time()

    try:
        while True:
            hdr, payload = read_frame(ser)
            if not hdr:
                continue

            t = hdr["type"]
            if t == PROTO_TYPE_STREAM:
                sample = decode_data_frame(hdr, payload)
                gap = (sample.seq - last_seq) if last_seq is not None else 0
                last_seq = sample.seq
                v = sample.values
                print(f'seq={sample.seq:8d} ts={sample.ts_ms:10d} '
                      f'I={v["I"]:4d}mA V={v["V"]:4d}mV P={v["P"]:5d}mW gap={gap:3d}')
                frames += 1
                if frames % 200 == 0:
                    dt = time.time() - t0
                    if dt > 0:
                        print(f'~{frames/dt:.1f} frames/s')
                    frames = 0
                    t0 = time.time()

            elif t in (PROTO_TYPE_ACK, PROTO_TYPE_NACK):
                ev = parse_control_frame(hdr, payload)
                print(format_control_event(ev))

            else:
                print(f'OTHER type={t} len={hdr["len"]} seq={hdr["seq"]}')

    except KeyboardInterrupt:
        pass
    finally:
        try:
            ser.close()
        except Exception:
            pass

if __name__ == '__main__':
    main()
