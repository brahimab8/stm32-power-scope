from __future__ import annotations

import pytest

from host.model.channel import Channel, ChannelReading


def test_measured_channel_requires_encode():
    with pytest.raises(ValueError):
        Channel(channel_id=1, name="v", is_measured=True, encode=None)


def test_measured_channel_rejects_compute_block():
    with pytest.raises(ValueError):
        Channel(
            channel_id=1,
            name="v",
            is_measured=True,
            encode="uint16",
            compute={"operation": "add", "channels": [1]},
        )


def test_computed_channel_requires_compute_and_rejects_encode():
    with pytest.raises(ValueError):
        Channel(channel_id=2, name="p", is_measured=False, compute=None)

    with pytest.raises(ValueError):
        Channel(
            channel_id=2,
            name="p",
            is_measured=False,
            encode="uint16",
            compute={"operation": "add", "channels": [1]},
        )


def test_computed_channel_requires_operation_and_channels():
    with pytest.raises(ValueError):
        Channel(channel_id=2, name="p", is_measured=False, compute={"channels": [1]})

    with pytest.raises(ValueError):
        Channel(channel_id=2, name="p", is_measured=False, compute={"operation": "add"})

    with pytest.raises(ValueError):
        Channel(channel_id=2, name="p", is_measured=False, compute={"operation": "add", "channels": "nope"})


def test_computed_channel_validates_inputs_and_factor():
    with pytest.raises(ValueError):
        Channel(
            channel_id=2,
            name="p",
            is_measured=False,
            compute={"operation": "add", "channels": [1], "inputs": "nope"},
        )

    with pytest.raises(ValueError):
        Channel(
            channel_id=2,
            name="p",
            is_measured=False,
            compute={"operation": "add", "channels": [1], "factor": "x"},
        )


def test_invalid_endian_raises():
    with pytest.raises(ValueError):
        Channel(channel_id=1, name="v", encode="uint16", endian="middle")


def test_size_is_zero_for_computed():
    ch = Channel(
        channel_id=2,
        name="p",
        is_measured=False,
        compute={"operation": "add", "channels": [1]},
    )
    assert ch.size == 0


def test_decode_raw_bytes_little_endian_uint16():
    ch = Channel(channel_id=1, name="v", encode="uint16", endian="little")
    assert ch.decode_raw_bytes(b"\x34\x12") == 0x1234


def test_decode_raw_bytes_big_endian_uint16():
    ch = Channel(channel_id=1, name="v", encode="uint16", endian="big")
    assert ch.decode_raw_bytes(b"\x12\x34") == 0x1234


def test_decode_raw_bytes_on_computed_raises():
    ch = Channel(
        channel_id=2,
        name="p",
        is_measured=False,
        compute={"operation": "add", "channels": [1]},
    )
    with pytest.raises(RuntimeError):
        ch.decode_raw_bytes(b"\x00")


def test_to_display_units_applies_lsb_and_scale():
    ch = Channel(channel_id=1, name="v", encode="uint16", lsb=0.5, scale=2.0)
    assert ch.to_display_units(10.0) == 10.0 * 0.5 * 2.0


def test_evaluate_computed_missing_deps_raises():
    ch = Channel(
        channel_id=10,
        name="sum",
        is_measured=False,
        compute={"operation": "add", "channels": [1, 2]},
    )
    with pytest.raises(ValueError):
        ch.evaluate_computed({})


def test_evaluate_computed_uses_value_or_raw_and_applies_factor():
    deps = {
        1: ChannelReading(channel_id=1, name="a", is_measured=True, raw=10.0, value=1.0, unit=""),
        2: ChannelReading(channel_id=2, name="b", is_measured=True, raw=20.0, value=2.0, unit=""),
    }

    ch_value = Channel(
        channel_id=10,
        name="sum_v",
        is_measured=False,
        compute={"operation": "add", "channels": [1, 2], "inputs": "value", "factor": 2.0},
    )
    assert ch_value.evaluate_computed(deps) == (1.0 + 2.0) * 2.0

    ch_raw = Channel(
        channel_id=11,
        name="sum_r",
        is_measured=False,
        compute={"operation": "add", "channels": [1, 2], "inputs": "raw", "factor": 0.5},
    )
    assert ch_raw.evaluate_computed(deps) == (10.0 + 20.0) * 0.5


def test_evaluate_computed_dep_missing_requested_field_raises():
    deps = {
        1: ChannelReading(channel_id=1, name="a", is_measured=True, raw=None, value=1.0, unit=""),
    }
    ch = Channel(
        channel_id=10,
        name="need_raw",
        is_measured=False,
        compute={"operation": "add", "channels": [1], "inputs": "raw"},
    )
    with pytest.raises(ValueError):
        ch.evaluate_computed(deps)
