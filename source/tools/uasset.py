"""Minimal UE4.27 cooked (unversioned header, split .uexp) package editor.
Supports: adding names, adding imports, extending preload deps, replacing export data."""
import struct

def rstr(b, p):
    n, = struct.unpack_from('<i', b, p); p += 4
    if n == 0: return '', p
    if n < 0: n = -n; return b[p:p+2*n].decode('utf-16-le')[:-1], p + 2*n
    return b[p:p+n-1].decode('latin-1'), p + n

def wstr(s):
    if s == '': return struct.pack('<i', 0)
    try: e = s.encode('ascii'); return struct.pack('<i', len(e)+1) + e + b'\0'
    except UnicodeEncodeError: e = s.encode('utf-16-le'); return struct.pack('<i', -(len(e)//2+1)) + e + b'\0\0'

_T = []
for _i in range(256):
    _c = _i << 24
    for _ in range(8): _c = ((_c << 1) ^ 0x04C11DB7) & 0xffffffff if _c & 0x80000000 else (_c << 1) & 0xffffffff
    _T.append(_c)

def name_hashes(s):
    import zlib
    h = 0
    for ch in s:
        c = ord(ch.upper()) if ord(ch) < 128 else ord(ch)
        h = ((h >> 8) & 0x00FFFFFF) ^ _T[(h ^ c) & 0xFF]
    crc = zlib.crc32(b''.join(struct.pack('<I', ord(c)) for c in s))
    return struct.pack('<HH', h & 0xffff, crc & 0xffff)

EXP = struct.Struct('<iiiiiiIqqiii16sIiiiiiii')

class Package:
    def __init__(self, uasset_bytes, uexp_bytes):
        b = self.b = uasset_bytes; self.uexp = uexp_bytes; self.orig_uexp = uexp_bytes; self.replaced = {}
        p = 0; f = {}
        def i32(name):
            nonlocal p; f[name] = (p, struct.unpack_from('<i', b, p)[0]); p += 4
        p = 4 + 4 + 4 + 4 + 4
        nc, = struct.unpack_from('<i', b, p); p += 4 + nc * 20
        i32('TotalHeaderSize')
        _, p = rstr(b, p)
        p += 4  # flags
        i32('NameCount'); i32('NameOffset')
        i32('GatherCount'); i32('GatherOffset')
        i32('ExportCount'); i32('ExportOffset'); i32('ImportCount'); i32('ImportOffset'); i32('DependsOffset')
        i32('SoftCount'); i32('SoftOffset'); i32('SearchableOffset'); i32('ThumbOffset')
        p += 16
        gc, = struct.unpack_from('<i', b, p); p += 4
        f['Gen'] = (p, None); p += 8 * gc
        for _ in range(2):
            p += 10; _, p = rstr(b, p)
        p += 4
        cc, = struct.unpack_from('<i', b, p); p += 4 + cc * 0  # assume 0
        assert cc == 0
        p += 4
        ac, = struct.unpack_from('<i', b, p); p += 4; assert ac == 0
        i32('AssetRegistryOffset')
        f['BulkStart'] = (p, struct.unpack_from('<q', b, p)[0]); p += 8
        i32('WorldTileOffset')
        ch, = struct.unpack_from('<i', b, p); p += 4 + 4 * ch
        i32('PreloadCount'); i32('PreloadOffset')
        self.f = f
        v = lambda k: f[k][1]
        assert v('GatherCount') == 0 and v('SoftCount') == 0
        # names
        p = v('NameOffset'); self.names = []; self.hashes = {}
        for _ in range(v('NameCount')):
            s, p = rstr(b, p); self.hashes[s] = b[p:p+4]; p += 4; self.names.append(s)
        assert p == v('ImportOffset'), (p, v('ImportOffset'))
        self.imports = []
        for i in range(v('ImportCount')):
            self.imports.append(list(struct.unpack_from('<qqiq', b, p))); p += 28
        assert p == v('ExportOffset')
        self.exports = []
        for i in range(v('ExportCount')):
            self.exports.append(list(EXP.unpack_from(b, p))); p += EXP.size
        assert p == v('DependsOffset')
        self.depends_blob = b[p:v('AssetRegistryOffset')]
        self.ar_blob = b[v('AssetRegistryOffset'):v('PreloadOffset')]
        self.preload = list(struct.unpack_from('<%di' % v('PreloadCount'), b, v('PreloadOffset')))
        assert v('PreloadOffset') + 4 * v('PreloadCount') == len(b)
        self.head = bytearray(b[:v('NameOffset')])

    def export_data(self, i):
        e = self.exports[i]; hdr = self.f['TotalHeaderSize'][1]
        return self.orig_uexp[e[8] - hdr:e[8] - hdr + e[7]]

    def replace_export(self, i, data):
        self.replaced[i] = data

    def name(self, s):
        if s not in self.names: self.names.append(s)
        return self.names.index(s)
    def fname(self, packed):
        return self.names[packed & 0xffffffff] + ('' if packed >> 32 == 0 else '_%d' % ((packed >> 32) - 1))
    def find_import(self, objname):
        for i, im in enumerate(self.imports):
            if self.fname(im[3]) == objname: return -i - 1
    def add_import(self, class_pkg, class_name, outer, obj):
        self.imports.append([self.name(class_pkg), self.name(class_name), outer, self.name(obj)])
        return -len(self.imports)

    def build(self, new_uexp=None):
        if new_uexp is not None: self.uexp = new_uexp
        names = b''.join(wstr(s) + self.hashes.get(s, name_hashes(s)) for s in self.names)
        imps = b''.join(struct.pack('<qqiq', *im) for im in self.imports)
        no = len(self.head); io = no + len(names); eo = io + len(imps)
        do = eo + EXP.size * len(self.exports)
        aro = do + len(self.depends_blob); po = aro + len(self.ar_blob)
        total = po + 4 * len(self.preload)
        if len(self.exports) == 1:
            ex = self.exports[0]
            body = len(self.uexp) - 4
            ex[7] = body; ex[8] = total
        else:
            # exports are laid out back to back in the uexp, followed by the package tag
            hdr = self.f['TotalHeaderSize'][1]
            order = sorted(range(len(self.exports)), key=lambda i: self.exports[i][8])
            chunks, pos = [], total
            for i in order:
                e = self.exports[i]
                data = self.replaced.get(i)
                if data is None:
                    data = self.orig_uexp[e[8] - hdr:e[8] - hdr + e[7]]
                e[7] = len(data); e[8] = pos; pos += len(data); chunks.append(data)
            self.uexp = b''.join(chunks) + self.orig_uexp[-4:]
            body = len(self.uexp) - 4
        h = self.head
        def put(k, val, fmt='<i'): struct.pack_into(fmt, h, self.f[k][0], val)
        put('TotalHeaderSize', total); put('NameCount', len(self.names)); put('NameOffset', no)
        put('ImportCount', len(self.imports)); put('ImportOffset', io); put('ExportOffset', eo)
        put('ExportCount', len(self.exports))
        put('DependsOffset', do); put('AssetRegistryOffset', aro); put('PreloadCount', len(self.preload))
        put('PreloadOffset', po); put('BulkStart', total + body, '<q')
        gp = self.f['Gen'][0]; struct.pack_into('<ii', h, gp, len(self.exports), len(self.names))
        if self.f['SearchableOffset'][1]: raise RuntimeError('searchable names unsupported')
        out = bytes(h) + names + imps + b''.join(EXP.pack(*e) for e in self.exports) + self.depends_blob + self.ar_blob + struct.pack('<%di' % len(self.preload), *self.preload)
        assert len(out) == total
        return out, self.uexp
