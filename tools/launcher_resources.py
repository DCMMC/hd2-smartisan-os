"""Read simple integer entries from this KitKat resources.arsc, preserving IDs."""
import re
import struct


def fit_hd2(data):
    data = bytearray(data)

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

    changes = []
    for p, kind, header, size in chunks(12, len(data)):
        if kind != 0x200:
            continue
        types = pool(p+struct.unpack_from('<I', data, p+268)[0])
        keys = pool(p+struct.unpack_from('<I', data, p+276)[0])
        for q, kind2, h2, size2 in chunks(p+header, p+size):
            if kind2 != 0x201 or types[data[q+8]-1] != 'integer':
                continue
            assert data[q+9] == 0, 'Sparse/compact entries unsupported'
            count, start = struct.unpack_from('<II', data, q+12)
            entries = {}
            for i in range(count):
                offset = struct.unpack_from('<I', data, q+h2+4*i)[0]
                if offset == 0xffffffff:
                    continue
                e = q+start+offset
                es, flags, key = struct.unpack_from('<HHI', data, e)
                if flags & 1 or data[e+es+3] != 16:
                    continue
                entries[keys[key]] = (e+es+4, struct.unpack_from('<i', data, e+es+4)[0])
            if 'screen_width' not in entries:
                continue
            width = entries['screen_width'][1]
            assert width in (720, 1080)
            ratio = 480 / width
            fixed = {'screen_width': 480, 'window_width': 480,
                     'screen_height': 800, 'window_height': 800,
                     # Match the current Smartisan framework's status bar.
                     'status_bar_height': 52}
            for name, (offset, old) in entries.items():
                base = re.sub(r'_\d+$', '', name)
                spatial = (re.search(r'width|height|size|spacing|margin|distance|offset|off_set|font|translate|_w$|_h$', base)
                           and not re.search(r'scale|percent|color|length|count|duration', base))
                if name in fixed:
                    new = fixed[name]
                elif spatial or base in ('magnify_stencil_radius', 'app_text_shadow_radius',
                                         'app_text_shadow_dx', 'app_text_shadow_dy'):
                    new = round(old * ratio)
                    if old and not new:
                        new = 1 if old > 0 else -1
                else:
                    continue
                if new != old:
                    struct.pack_into('<i', data, offset, new)
                    changes.append({'name': name, 'donor_width': width, 'from': old, 'to': new})
    assert len([r for r in changes if r['name'] == 'screen_width']) == 2
    return data, changes
