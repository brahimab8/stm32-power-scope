from __future__ import annotations

import math
import pytest

from host.model.codec import decode_primitive, primitive_size


def test_primitive_size_known_types():
    assert primitive_size("uint8") == 1
    assert primitive_size("int16") == 2
    assert primitive_size("uint32") == 4
    assert primitive_size("double") == 8


def test_primitive_size_unknown_raises():
    with pytest.raises(NotImplementedError):
        primitive_size("u128")


def test_decode_uint16_endian():
    assert decode_primitive("uint16", b"\x34\x12", endian="little") == 0x1234
    assert decode_primitive("uint16", b"\x12\x34", endian="big") == 0x1234


def test_decode_int16_signed():
    assert decode_primitive("int16", b"\xFF\xFF", endian="little") == -1
    assert decode_primitive("int16", b"\x80\x00", endian="big") == -32768


def test_decode_float_endian():
    # 1.0 as IEEE754
    assert decode_primitive("float", b"\x00\x00\x80\x3F", endian="little") == 1.0
    assert decode_primitive("float", b"\x3F\x80\x00\x00", endian="big") == 1.0


def test_decode_wrong_size_raises():
    with pytest.raises(ValueError):
        decode_primitive("uint32", b"\x01\x02\x03", endian="little")


def test_decode_unknown_encode_raises():
    with pytest.raises(NotImplementedError):
        decode_primitive("nope", b"\x00", endian="little")
