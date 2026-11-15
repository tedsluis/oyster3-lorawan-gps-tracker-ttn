import pytest

from oyster3.bits import BitReader, BitWriter, read_field


def test_reader_is_lsb_first_within_a_byte():
    # Spec Uplink 2 example: 0xD3 -> bits 0-6 = 83 (sequence), bit 7 = 1 (accepted)
    reader = BitReader(bytes.fromhex("D3"))
    assert reader.u(7) == 83
    assert reader.u(1) == 1


def test_reader_crosses_byte_boundaries_little_endian():
    # 11 bits starting at bit 5: low 3 bits from byte 0, next 8 bits from byte 1
    data = bytes([0b1010_0000, 0b0000_0001])
    assert read_field(data, 5, 4) == 0b1101
    assert BitReader(bytes.fromhex("3412")).u(16) == 0x1234


def test_reader_signed_twos_complement():
    assert read_field(bytes([0b11101]), 0, 5, signed=True) == -3
    assert read_field(bytes([0b01111]), 0, 5, signed=True) == 15


def test_reader_refuses_to_read_past_the_end():
    reader = BitReader(b"\x00")
    reader.u(7)
    with pytest.raises(ValueError, match="past end"):
        reader.u(2)


def test_writer_mirrors_reader():
    writer = BitWriter(3)
    writer.write(0, 7, 83)
    writer.write(7, 1, 1)
    writer.write(13, 9, -100, signed=True)
    data = writer.to_bytes()
    assert data[0] == 0xD3
    assert read_field(data, 13, 9, signed=True) == -100


@pytest.mark.parametrize(
    "start, nbits, value, signed",
    [(0, 8, 256, False), (0, 8, -1, False), (0, 5, 16, True), (0, 5, -17, True), (4, 8, 1, False)],
)
def test_writer_rejects_values_that_do_not_fit(start, nbits, value, signed):
    with pytest.raises(ValueError):
        BitWriter(1).write(start, nbits, value, signed=signed)


def test_writer_rejects_overlapping_fields():
    writer = BitWriter(1)
    writer.write(0, 4, 1)
    with pytest.raises(ValueError, match="overlaps"):
        writer.write(3, 2, 0)
