"""UE4.27 .locres (v3) reader/writer that preserves stored key/source hashes."""
import struct

MAGIC = bytes.fromhex('0E14747567 4A03FC4A15909DC3377F1B'.replace(' ', ''))

def rstr(b, p):
    n, = struct.unpack_from('<i', b, p); p += 4
    if n == 0: return '', p
    if n < 0:
        n = -n; return b[p:p+2*n].decode('utf-16-le')[:-1], p + 2*n
    return b[p:p+n].decode('latin-1')[:-1], p + n

def wstr(s):
    if s == '': return struct.pack('<i', 0)
    try:
        e = s.encode('ascii'); return struct.pack('<i', len(e) + 1) + e + b'\0'
    except UnicodeEncodeError:
        e = s.encode('utf-16-le'); return struct.pack('<i', -(len(e)//2 + 1)) + e + b'\0\0'

def read(path):
    b = open(path, 'rb').read()
    assert b[:16] == MAGIC, 'not v2+ locres'
    ver = b[16]; p = 17
    soff, = struct.unpack_from('<q', b, p); p += 8
    if ver >= 2: p += 4
    q = soff; n, = struct.unpack_from('<i', b, q); q += 4
    strings = []
    for _ in range(n):
        s, q = rstr(b, q)
        if ver >= 2: q += 4
        strings.append(s)
    nns, = struct.unpack_from('<I', b, p); p += 4
    out = []  # list of (nshash, ns, keyhash, key, srchash, text)
    for _ in range(nns):
        nh = 0
        if ver >= 2: nh, = struct.unpack_from('<I', b, p); p += 4
        ns, p = rstr(b, p)
        nk, = struct.unpack_from('<I', b, p); p += 4
        for _ in range(nk):
            kh = 0
            if ver >= 2: kh, = struct.unpack_from('<I', b, p); p += 4
            k, p = rstr(b, p)
            sh, si = struct.unpack_from('<Ii', b, p); p += 8
            out.append((nh, ns, kh, k, sh, strings[si]))
    return ver, out

def write(path, entries):
    """entries: list of (nshash, ns, keyhash, key, srchash, text). Writes v3 with string dedup."""
    from collections import OrderedDict
    nss = OrderedDict()
    for nh, ns, kh, k, sh, t in entries:
        nss.setdefault((nh, ns), []).append((kh, k, sh, t))
    strings = []; sidx = {}; refs = []
    body = bytearray(struct.pack('<I', len(nss)))
    for (nh, ns), keys in nss.items():
        body += struct.pack('<I', nh) + wstr(ns) + struct.pack('<I', len(keys))
        for kh, k, sh, t in keys:
            if t not in sidx: sidx[t] = len(strings); strings.append(t); refs.append(0)
            refs[sidx[t]] += 1
            body += struct.pack('<I', kh) + wstr(k) + struct.pack('<Ii', sh, sidx[t])
    head_len = 16 + 1 + 8 + 4
    soff = head_len + len(body)
    tail = bytearray(struct.pack('<i', len(strings)))
    for s, r in zip(strings, refs): tail += wstr(s) + struct.pack('<i', r)
    data = MAGIC + bytes([3]) + struct.pack('<qI', soff, len(entries)) + bytes(body) + bytes(tail)
    open(path, 'wb').write(data)
