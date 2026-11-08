"""Tagged-property (de)serializer for UE4.27 cooked exports. Values of leaf types kept as raw bytes."""
import struct, copy

# Structs serialized natively (no property tags) in cooked 4.27 data.
NATIVE_STRUCTS = {'FontData', 'Vector2D', 'LinearColor', 'Color', 'Vector', 'Vector4', 'Guid', 'Box2D', 'IntPoint',
                  'Rotator', 'Quat', 'Box', 'DateTime', 'Timespan', 'FrameNumber', 'SoftObjectPath', 'Int32Point'}

class Prop:
    def __init__(self, name, type, **kw):
        self.name = name; self.type = type; self.__dict__.update(kw)
    def __repr__(self): return 'Prop(%s:%s)' % (self.name, self.type)

class Reader:
    def __init__(self, pkg, data): self.pkg = pkg; self.d = data
    def fn(self, p): v, = struct.unpack_from('<q', self.d, p); return self.pkg.fname(v), p + 8
    def tag(self, p):
        name, p = self.fn(p)
        if name == 'None': return None, p
        typ, p = self.fn(p)
        size, idx = struct.unpack_from('<ii', self.d, p); p += 8
        t = Prop(name, typ, idx=idx)
        if typ == 'StructProperty':
            t.struct, p = self.fn(p); t.sguid = self.d[p:p+16]; p += 16
        elif typ in ('ByteProperty', 'EnumProperty'):
            t.enum, p = self.fn(p)
        elif typ == 'ArrayProperty':
            t.inner, p = self.fn(p)
        elif typ == 'BoolProperty':
            t.bval = self.d[p]; p += 1
        elif typ in ('SetProperty',):
            t.inner, p = self.fn(p)
        elif typ == 'MapProperty':
            t.key, p = self.fn(p); t.inner, p = self.fn(p)
        hg = self.d[p]; p += 1
        assert hg == 0
        t.size = size
        return t, p
    def props(self, p):
        out = []
        while True:
            t, p = self.tag(p)
            if t is None: return out, p
            end = p + t.size
            self.value(t, p, end)
            out.append(t); p = end
    def value(self, t, p, end):
        if t.type == 'StructProperty' and t.struct not in NATIVE_STRUCTS:
            t.children, q = self.props(p); assert q == end, (t, q, end)
        elif t.type == 'ArrayProperty' and t.inner == 'StructProperty':
            n, = struct.unpack_from('<i', self.d, p); q = p + 4
            it, q = self.tag(q); t.itag = it; t.items = []
            for _ in range(n):
                if it.struct in NATIVE_STRUCTS: raise NotImplementedError
                ch, q = self.props(q); t.items.append(ch)
            assert q == end
        elif t.type == 'NameProperty' or t.type == 'EnumProperty' or (t.type == 'ByteProperty' and t.enum != 'None'):
            t.nameval, _ = self.fn(p)
        else:
            t.raw = self.d[p:end]

class Writer:
    def __init__(self, pkg): self.pkg = pkg
    def fn(self, s):
        import re
        m = re.match(r'^(.*)_(\d+)$', s)
        if m and s not in self.pkg.names and m.group(1) in self.pkg.names:
            return struct.pack('<iI', self.pkg.name(m.group(1)), int(m.group(2)) + 1)
        return struct.pack('<q', self.pkg.name(s))
    def tag(self, t, size):
        b = self.fn(t.name) + self.fn(t.type) + struct.pack('<ii', size, t.idx)
        if t.type == 'StructProperty': b += self.fn(t.struct) + t.sguid
        elif t.type in ('ByteProperty', 'EnumProperty'): b += self.fn(t.enum)
        elif t.type in ('ArrayProperty', 'SetProperty'): b += self.fn(t.inner)
        elif t.type == 'BoolProperty': b += bytes([t.bval])
        elif t.type == 'MapProperty': b += self.fn(t.key) + self.fn(t.inner)
        return b + b'\0'
    def props(self, lst):
        b = b''
        for t in lst:
            v = self.value(t); b += self.tag(t, len(v)) + v
        return b + self.fn('None')
    def value(self, t):
        if hasattr(t, 'children'): return self.props(t.children)
        if hasattr(t, 'items'):
            body = b''.join(self.props(ch) for ch in t.items)
            return struct.pack('<i', len(t.items)) + self.tag(t.itag, len(body)) + body
        if hasattr(t, 'nameval'): return self.fn(t.nameval)
        return t.raw

def find(lst, name):
    for t in lst:
        if t.name == name: return t
