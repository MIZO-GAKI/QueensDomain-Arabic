"""Minimal UE4 pak v11 reader (unencrypted index). Used for Queen's Domain Arabic localization."""
import struct, sys, os, hashlib

def rstr(b, p):
    n = struct.unpack_from('<i', b, p)[0]; p += 4
    if n == 0: return '', p
    if n < 0:
        n = -n; s = b[p:p+2*n].decode('utf-16-le').rstrip('\0'); return s, p + 2*n
    s = b[p:p+n].decode('utf-8', 'replace').rstrip('\0'); return s, p + n

class Pak:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        self.f.seek(-221, 2)
        ft = self.f.read(221)
        guid = ft[0:16]; enc = ft[16]
        magic, ver, ioff, isz = struct.unpack_from('<IIqq', ft, 17)
        assert magic == 0x5A6F12E1, hex(magic)
        self.version = ver; self.index_encrypted = enc
        names = ft[61:221]
        self.methods = [names[i*32:(i+1)*32].split(b'\0')[0].decode() for i in range(5)]
        assert not enc, 'index encrypted'
        self.f.seek(ioff); idx = self.f.read(isz)
        p = 0
        self.mount, p = rstr(idx, p)
        num, = struct.unpack_from('<i', idx, p); p += 4
        p += 8  # seed
        has_ph, = struct.unpack_from('<I', idx, p); p += 4
        if has_ph: p += 8 + 8 + 20
        has_fd, = struct.unpack_from('<I', idx, p); p += 4
        fdo, fds = struct.unpack_from('<qq', idx, p); p += 8 + 8 + 20
        esz, = struct.unpack_from('<i', idx, p); p += 4
        self.enc = idx[p:p+esz]; p += esz
        nfiles, = struct.unpack_from('<i', idx, p); p += 4
        self.raw_entries = []
        for _ in range(nfiles):
            e, p = self._read_entry(idx, p); self.raw_entries.append(e)
        self.f.seek(fdo); fd = self.f.read(fds)
        q = 0; ndirs, = struct.unpack_from('<i', fd, q); q += 4
        self.files = {}
        for _ in range(ndirs):
            d, q = rstr(fd, q)
            nf, = struct.unpack_from('<i', fd, q); q += 4
            for _ in range(nf):
                fn, q = rstr(fd, q)
                eo, = struct.unpack_from('<i', fd, q); q += 4
                self.files[(d + fn).lstrip('/')] = eo

    def _read_entry(self, b, p):
        off, sz, usz, cm = struct.unpack_from('<qqqI', b, p); p += 28
        p += 20
        blocks = []
        if cm:
            n, = struct.unpack_from('<I', b, p); p += 4
            for i in range(n):
                s, e = struct.unpack_from('<qq', b, p); p += 16; blocks.append((s, e))
        flags = b[p]; p += 1
        bs, = struct.unpack_from('<I', b, p); p += 4
        return dict(offset=off, size=sz, usize=usz, method=cm, blocks=blocks, enc=flags & 1, bs=bs), p

    def entry(self, name):
        eo = self.files[name]
        if eo < 0: return self.raw_entries[-eo - 1]
        b = self.enc; p = eo
        v, = struct.unpack_from('<I', b, p); p += 4
        bs = (v & 0x3f) << 11
        if (v & 0x3f) == 0x3f:
            bs, = struct.unpack_from('<I', b, p); p += 4
        nblk = (v >> 6) & 0xffff; enc = (v >> 22) & 1; cm = (v >> 23) & 0x3f
        def rd(safe):
            nonlocal p
            if safe: x, = struct.unpack_from('<I', b, p); p += 4
            else: x, = struct.unpack_from('<q', b, p); p += 8
            return x
        off = rd(v & (1 << 31)); usz = rd(v & (1 << 30))
        sz = rd(v & (1 << 29)) if cm else usz
        hdr = 8 + 8 + 8 + 4 + 20 + 1 + 4 + (4 + 16 * nblk if cm else 0)
        blocks = []
        if cm:
            if nblk == 1 and not enc:
                blocks = [(hdr, hdr + sz)]
            else:
                cur = hdr
                for i in range(nblk):
                    s, = struct.unpack_from('<I', b, p); p += 4
                    blocks.append((cur, cur + s)); cur += s if not enc else (s + 15) // 16 * 16
            blocks = [(off + s, off + e) for s, e in blocks]  # absolute
        return dict(offset=off, size=sz, usize=usz, method=cm, blocks=blocks, enc=enc, bs=bs, hdr=hdr)

    def read(self, name):
        e = self.entry(name)
        if e['enc']: raise RuntimeError('encrypted entry ' + name)
        if e['method'] == 0:
            hdr = e.get('hdr', 53)
            self.f.seek(e['offset'] + hdr); return self.f.read(e['usize'])
        m = self.methods[e['method'] - 1]
        out = bytearray()
        for s, en in e['blocks']:
            self.f.seek(s); c = self.f.read(en - s)
            if m.lower() == 'zlib':
                import zlib; out += zlib.decompress(c)
            elif m.lower() == 'oodle':
                raise RuntimeError('oodle')
            else: raise RuntimeError(m)
        return bytes(out)

if __name__ == '__main__':
    pk = Pak(sys.argv[1])
    cmd = sys.argv[2]
    if cmd == 'info':
        print('version', pk.version, 'mount', pk.mount, 'methods', pk.methods, 'files', len(pk.files))
    elif cmd == 'list':
        for n in sorted(pk.files):
            e = pk.entry(n); print(e['usize'], e['method'], e['enc'], n)
    elif cmd == 'extract':
        out = sys.argv[3]
        import re
        pat = re.compile(sys.argv[4])
        for n in sorted(pk.files):
            if pat.search(n):
                d = os.path.join(out, n); os.makedirs(os.path.dirname(d), exist_ok=True)
                open(d, 'wb').write(pk.read(n)); print('x', n)
