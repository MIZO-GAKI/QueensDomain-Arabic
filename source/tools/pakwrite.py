"""Write an uncompressed, unencrypted UE4.27 pak (version 11) from {pak_path: bytes}."""
import struct, hashlib

def fnv64_path(path, seed):
    data = path.lower().encode('utf-16-le')
    h = (0xcbf29ce484222325 + seed) & 0xFFFFFFFFFFFFFFFF
    for b in data: h = ((h ^ b) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h

def wstr(s):
    if s == '': return struct.pack('<i', 0)
    try: e = s.encode('ascii'); return struct.pack('<i', len(e)+1) + e + b'\0'
    except UnicodeEncodeError: e = s.encode('utf-16-le'); return struct.pack('<i', -(len(e)//2+1)) + e + b'\0\0'

def entry(off, size, sha):
    return struct.pack('<qqqI', off, size, size, 0) + sha + b'\0' + struct.pack('<I', 0)

def write(out, files, mount='../../../', seed=0):
    f = open(out, 'wb'); recs = []
    for name in sorted(files):
        data = files[name]; sha = hashlib.sha1(data).digest()
        off = f.tell(); f.write(entry(0, len(data), sha)); f.write(data)
        recs.append((name, off, len(data), sha))
    # directory index
    dirs = {'/': {}}
    for i, (name, *_ ) in enumerate(recs):
        parts = name.split('/'); d = '/'.join(parts[:-1]) + '/'
        acc = ''
        for p in parts[:-1]:
            acc += p + '/'; dirs.setdefault(acc, {})
        dirs[d][parts[-1]] = -(i + 1)   # negative -> Files array
    fd = struct.pack('<i', len(dirs))
    for d, fl in dirs.items():
        fd += wstr(d) + struct.pack('<i', len(fl))
        for fn, loc in fl.items(): fd += wstr(fn) + struct.pack('<i', loc)
    ph = struct.pack('<i', len(recs))
    for i, (name, *_ ) in enumerate(recs): ph += struct.pack('<Qi', fnv64_path(name, seed), -(i + 1))
    ph += fd  # pruned directory index (full)
    files_arr = struct.pack('<i', len(recs)) + b''.join(entry(o, s, h) for _, o, s, h in recs)
    # layout: data | primary index | path hash index | full dir index
    idx_off = f.tell()
    def build_primary(ph_off, fd_off):
        return (wstr(mount) + struct.pack('<iQ', len(recs), seed)
                + struct.pack('<Iqq', 1, ph_off, len(ph)) + hashlib.sha1(ph).digest()
                + struct.pack('<Iqq', 1, fd_off, len(fd)) + hashlib.sha1(fd).digest()
                + struct.pack('<i', 0) + files_arr)
    plen = len(build_primary(0, 0))
    primary = build_primary(idx_off + plen, idx_off + plen + len(ph))
    f.write(primary); f.write(ph); f.write(fd)
    f.write(b'\0' * 16 + b'\0' + struct.pack('<IIqq', 0x5A6F12E1, 11, idx_off, len(primary)) + hashlib.sha1(primary).digest() + b'\0' * 160)
    f.close()
