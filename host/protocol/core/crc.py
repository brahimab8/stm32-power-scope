def crc16(proto, buf: bytes) -> int:
    cfg = proto.constants.get("crc", {})
    seed = cfg.get("seed", 0xFFFF)
    poly = cfg.get("poly", 0x1021)

    crc = seed
    for b in buf:
        crc ^= (b & 0xFF) << 8
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFFFF if (crc & 0x8000) else ((crc << 1) & 0xFFFF)
    return crc
