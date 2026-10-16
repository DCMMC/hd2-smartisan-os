"""Read scalar entries in the old Android binary resource table in-place."""
import struct


def scalar_entries(data):
    def chunks(start, end):
        while start < end:
            kind, header, size = struct.unpack_from('<HHI', data, start)
            assert size >= header >= 8 and start+size <= end
            yield start, kind, header, size
            start += size

    def pool(pos):
        kind, header, size, count, styles, flags, start, unused = struct.unpack_from('<HH6I', data, pos)
        assert kind == 1
        def length(q):
            v = data[q]
            return (((v & 127) << 8) | data[q+1], q+2) if v & 128 else (v, q+1)
        result = []
        for i in range(count):
            q = pos+start+struct.unpack_from('<I', data, pos+header+4*i)[0]
            if flags & 256:
                _, q = length(q)
                n, q = length(q)
                result.append(data[q:q+n].decode('utf-8'))
            else:
                n = struct.unpack_from('<H', data, q)[0]
                assert n < 0x8000
                result.append(data[q+2:q+2+2*n].decode('utf-16le'))
        return result

    for p, kind, header, size in chunks(12, len(data)):
        if kind != 0x200:
            continue
        package = struct.unpack_from('<I', data, p+8)[0]
        types = pool(p+struct.unpack_from('<I', data, p+268)[0])
        keys = pool(p+struct.unpack_from('<I', data, p+276)[0])
        for q, kind2, h2, size2 in chunks(p+header, p+size):
            if kind2 != 0x201:
                continue
            assert data[q+9] == 0, 'Sparse/compact entries unsupported'
            type_id = data[q+8]
            count, start = struct.unpack_from('<II', data, q+12)
            density = struct.unpack_from('<H', data, q+34)[0]
            for i in range(count):
                offset = struct.unpack_from('<I', data, q+h2+4*i)[0]
                if offset == 0xffffffff:
                    continue
                e = q+start+offset
                es, flags, key = struct.unpack_from('<HHI', data, e)
                if flags & 1:
                    continue
                v = e+es
                yield {'id': package<<24 | type_id<<16 | i,
                       'type': types[type_id-1], 'name': keys[key],
                       'density': density, 'orientation': data[q+32],
                       'data_type': data[v+3],
                       'offset': v+4, 'value': struct.unpack_from('<I', data, v+4)[0]}


def dimension(value):
    mantissa = value & 0xffffff00
    if mantissa & 0x80000000:
        mantissa -= 0x100000000
    return mantissa * [1/256, 1/32768, 1/8388608, 1/2147483648][(value >> 4) & 3]
