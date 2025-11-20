from __future__ import annotations

import pytest

from host.model.channel import Channel
from host.model.sensor import Sensor


def test_invalid_payload_order_raises():
    with pytest.raises(ValueError):
        Sensor(type_id=1, name="s", payload_order="nope")


def test_duplicate_channel_id_raises():
    ch1 = Channel(channel_id=1, name="a", encode="uint8")
    ch2 = Channel(channel_id=1, name="b", encode="uint8")
    with pytest.raises(ValueError):
        Sensor(type_id=1, name="s", channels=[ch1, ch2])


def test_computed_channel_dep_missing_raises():
    meas = Channel(channel_id=1, name="a", encode="uint8")
    comp = Channel(
        channel_id=2,
        name="sum",
        is_measured=False,
        compute={"operation": "add", "channels": [99]},
    )
    with pytest.raises(ValueError):
        Sensor(type_id=1, name="s", channels=[meas, comp])


def test_expected_payload_size_is_sum_of_measured_sizes():
    a = Channel(channel_id=2, name="a", encode="uint16")
    b = Channel(channel_id=1, name="b", encode="uint8")
    c = Channel(channel_id=3, name="c", is_measured=False, compute={"operation": "add", "channels": [1]})

    s = Sensor(type_id=1, name="s", channels=[a, b, c])
    assert s.expected_payload_size() == 3  # uint16(2) + uint8(1)


def test_measured_channels_order_channel_id():
    a = Channel(channel_id=2, name="a", encode="uint8")
    b = Channel(channel_id=1, name="b", encode="uint8")
    s = Sensor(type_id=1, name="s", channels=[a, b], payload_order="channel_id")
    assert [ch.channel_id for ch in s.measured_channels()] == [1, 2]


def test_measured_channels_order_insertion():
    a = Channel(channel_id=2, name="a", encode="uint8")
    b = Channel(channel_id=1, name="b", encode="uint8")
    s = Sensor(type_id=1, name="s", channels=[a, b], payload_order="insertion")
    assert [ch.channel_id for ch in s.measured_channels()] == [2, 1]


def test_decode_payload_too_short_raises():
    a = Channel(channel_id=1, name="a", encode="uint16")
    s = Sensor(type_id=1, name="s", channels=[a])

    with pytest.raises(ValueError):
        s.decode_payload(b"\x01")  # need 2 bytes


def test_decode_payload_strict_length_mismatch_raises():
    a = Channel(channel_id=1, name="a", encode="uint8")
    s = Sensor(type_id=1, name="s", channels=[a])

    with pytest.raises(ValueError):
        s.decode_payload(b"\x01\x02", strict_length=True)


def test_decode_payload_decodes_measured_and_applies_scale():
    a = Channel(channel_id=1, name="a", encode="uint16", lsb=0.5, scale=2.0, display_unit="u")
    b = Channel(channel_id=2, name="b", encode="uint8", lsb=1.0, scale=1.0, display_unit="v")

    s = Sensor(type_id=1, name="s", channels=[a, b], payload_order="channel_id")

    # channel_id order -> a then b
    payload = b"\x34\x12" + b"\x05"  # a=0x1234, b=5
    r = s.decode_payload(payload, compute=False)

    assert r.measured[1].raw == 0x1234
    assert r.measured[1].value == 0x1234 * 0.5 * 2.0
    assert r.measured[1].unit == "u"

    assert r.measured[2].raw == 5.0
    assert r.measured[2].value == 5.0
    assert r.measured[2].unit == "v"
    assert r.computed == {}


def test_compute_channels_supports_chaining():
    a = Channel(channel_id=1, name="a", encode="uint8", display_unit="u")
    b = Channel(channel_id=2, name="b", encode="uint8", display_unit="u")

    c = Channel(
        channel_id=10,
        name="sum",
        is_measured=False,
        display_unit="u",
        compute={"operation": "add", "channels": [1, 2], "inputs": "raw"},
    )
    d = Channel(
        channel_id=11,
        name="double_sum",
        is_measured=False,
        display_unit="u",
        compute={"operation": "multiply", "channels": [10], "inputs": "raw", "factor": 2.0},
    )

    s = Sensor(type_id=1, name="s", channels=[a, b, c, d])

    r = s.decode_payload(b"\x03\x04", compute=True, strict_length=True)

    assert r.computed[10].raw == 7.0
    assert r.computed[11].raw == 14.0
    assert 10 in r.all and 11 in r.all
