"""LSb-first bit access, equivalent to MakeBitParser in the Digital Matter spec (§3.3.4).

Bit ``b.n`` in the spec is bit ``n`` (0 = least significant) of byte ``b``. A field that
crosses a byte boundary continues in the low bits of the next byte, i.e. the whole payload
is one little-endian integer and a field starts at bit ``byte * 8 + bit``.
"""


def to_unsigned(value: int, nbits: int) -> int:
    """Two's complement representation of a signed value in ``nbits`` bits."""
    if not -(1 << (nbits - 1)) <= value < (1 << (nbits - 1)):
        raise ValueError(f"{value} does not fit in a signed {nbits}-bit field")
    return value & ((1 << nbits) - 1)


class BitReader:
    def __init__(self, data: bytes):
        self._value = int.from_bytes(bytes(data), "little")
        self.bit_length = len(data) * 8
        self.offset = 0

    def u(self, nbits: int) -> int:
        if nbits <= 0:
            raise ValueError("nbits must be positive")
        if self.offset + nbits > self.bit_length:
            raise ValueError(
                f"read past end of data: need {nbits} bits at offset {self.offset}, "
                f"have {self.bit_length}"
            )
        value = (self._value >> self.offset) & ((1 << nbits) - 1)
        self.offset += nbits
        return value

    def s(self, nbits: int) -> int:
        value = self.u(nbits)
        if value & (1 << (nbits - 1)):
            value -= 1 << nbits
        return value

    def skip(self, nbits: int) -> None:
        if nbits:
            self.u(nbits)


def read_field(data: bytes, start: int, nbits: int, signed: bool = False) -> int:
    reader = BitReader(data)
    reader.skip(start)
    return reader.s(nbits) if signed else reader.u(nbits)


class BitWriter:
    def __init__(self, nbytes: int):
        self.nbytes = nbytes
        self._value = 0
        self._used = 0

    def write(self, start: int, nbits: int, value: int, signed: bool = False) -> None:
        if nbits <= 0:
            raise ValueError("nbits must be positive")
        if start < 0 or start + nbits > self.nbytes * 8:
            raise ValueError(f"field at bit {start} with {nbits} bits exceeds {self.nbytes} bytes")
        if signed:
            value = to_unsigned(value, nbits)
        elif not 0 <= value < (1 << nbits):
            raise ValueError(f"{value} does not fit in an unsigned {nbits}-bit field")
        mask = ((1 << nbits) - 1) << start
        if self._used & mask:
            raise ValueError(f"field at bit {start} overlaps an earlier field")
        self._used |= mask
        self._value |= value << start

    def to_bytes(self) -> bytes:
        return self._value.to_bytes(self.nbytes, "little")
