"""Read-only cooked-widget inventory; also useful without Unreal Editor."""
import argparse
import json
import struct
from pathlib import Path
from pak import Pak
from uasset import Package
import props


def ref(pkg, index):
    if index < 0:
        return pkg.fname(pkg.imports[-index - 1][3])
    if index > 0:
        e = pkg.exports[index - 1]
        return pkg.fname(e[4] | (e[5] << 32))
    return None


def value(pkg, p):
    if hasattr(p, 'children'):
        return {c.name: value(pkg, c) for c in p.children}
    if hasattr(p, 'items'):
        return [{c.name: value(pkg, c) for c in row} for row in p.items]
    if hasattr(p, 'nameval'):
        return p.nameval
    if p.type == 'BoolProperty':
        return bool(p.bval)
    if p.type in ('IntProperty', 'ObjectProperty'):
        v = struct.unpack('<i', p.raw)[0]
        return ref(pkg, v) if p.type == 'ObjectProperty' else v
    if p.type == 'FloatProperty':
        return struct.unpack('<f', p.raw)[0]
    if p.type == 'StructProperty' and p.struct in ('Vector2D', 'LinearColor'):
        return list(struct.unpack('<' + 'f' * (len(p.raw)//4), p.raw))
    return {'type': p.type, 'bytes': len(p.raw), 'hex': p.raw.hex()}


def audit(pak):
    widgets, errors = {}, []
    for path in sorted(pak.files):
        if not path.endswith('.uasset'):
            continue
        a = pak.read(path)
        if b'WidgetBlueprintGeneratedClass' not in a:
            continue
        try:
            pkg = Package(a, pak.read(path[:-7] + '.uexp'))
            if not any(ref(pkg, e[0]) == 'WidgetBlueprintGeneratedClass' for e in pkg.exports):
                continue
            exports = []
            for i, e in enumerate(pkg.exports):
                cls = ref(pkg, e[0])
                if cls in ('Function', 'WidgetBlueprintGeneratedClass') or (cls or '').startswith('MovieScene'):
                    continue
                try:
                    ps, end = props.Reader(pkg, pkg.export_data(i)).props(0)
                    exports.append(dict(index=i+1, name=ref(pkg, i+1), cls=cls,
                                        outer=ref(pkg, e[3]), properties={p.name: value(pkg, p) for p in ps}))
                except Exception as ex:
                    errors.append(dict(path=path, export=pkg.fname(e[4]), error=repr(ex)))
            widgets[path[:-7]] = exports
        except Exception as ex:
            errors.append(dict(path=path, error=repr(ex)))
    return dict(widgets=widgets, errors=errors)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('pak')
    ap.add_argument('output')
    args = ap.parse_args()
    result = audit(Pak(args.pak))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('widget packages:', len(result['widgets']), 'parse errors:', len(result['errors']))
