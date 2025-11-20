from __future__ import annotations

import pytest

from host.protocol.core.crc import crc16


class FakeProto:
    def __init__(self, *, seed=0xFFFF, poly=0x1021):
        self.constants = {
            "crc": {
                "seed": seed,
                "poly": poly,
            }
        }


def test_crc16_empty_buffer_returns_seed():
    proto = FakeProto(seed=0xABCD)
    assert crc16(proto, b"") == 0xABCD


def test_crc16_known_ccitt_vector():
    """
    CRC-16/CCITT-FALSE
    poly=0x1021, seed=0xFFFF
    ASCII "123456789" -> 0x29B1
    """
    proto = FakeProto(seed=0xFFFF, poly=0x1021)
    assert crc16(proto, b"123456789") == 0x29B1


def test_crc16_different_seed_changes_result():
    proto1 = FakeProto(seed=0xFFFF, poly=0x1021)
    proto2 = FakeProto(seed=0x0000, poly=0x1021)

    data = b"\x01\x02\x03"
    assert crc16(proto1, data) != crc16(proto2, data)


def test_crc16_different_poly_changes_result():
    proto1 = FakeProto(seed=0xFFFF, poly=0x1021)
    proto2 = FakeProto(seed=0xFFFF, poly=0x8005)

    data = b"\x10\x20\x30"
    assert crc16(proto1, data) != crc16(proto2, data)
