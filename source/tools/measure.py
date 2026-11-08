"""Glyph-advance text measurement matching the game's composite font (Rockwell + Arabic sub-font)."""
import struct, os
from ttf import tables, cmap
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Face:
    def __init__(self, path):
        d = open(path, 'rb').read(); t = tables(d)
        self.upem, = struct.unpack_from('>H', d, t['head'][0] + 18)
        nh, = struct.unpack_from('>H', d, t['hhea'][0] + 34)
        o = t['hmtx'][0]
        self.adv = [struct.unpack_from('>H', d, o + 4 * i)[0] for i in range(nh)]
        self.cmap = cmap(d)
    def advance(self, ch):
        g = self.cmap.get(ord(ch))
        if g is None: return None
        return self.adv[min(g, len(self.adv) - 1)] / self.upem

AR = Face(os.path.join(ROOT, 'assets/fonts/NotoNaskhArabicUI-Regular.ttf'))
LAT = None   # game's Rockwell face; loaded from the user's own game pak by load_latin()
ROCKWELL = 'QueensDomain/Content/UI/UI_Style/FontStyles/Rockwell_str_reg.ufont'


def load_latin(pak):
    global LAT
    tmp = os.path.join(ROOT, 'work', '_rockwell.ufont')
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    open(tmp, 'wb').write(pak.read(ROCKWELL))
    LAT = Face(tmp)
AR_RANGES = [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)]

def width(text, size, ar_scale=1.15):
    """Width in Slate units (font size is in points at 96 DPI)."""
    px = size * 96.0 / 72.0
    w = 0.0
    for ch in text:
        o = ord(ch)
        if any(a <= o <= b for a, b in AR_RANGES):
            a = AR.advance(ch); w += (a or 0.5) * px * ar_scale
        else:
            a = LAT.advance(ch)
            if a is None: a = AR.advance(ch) or 0.5
            w += a * px
    return w
