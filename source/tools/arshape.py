"""Arabic contextual shaping into Unicode Presentation Forms-B, for widgets that draw characters one by one
(the game's FB_AnimRichTextBlock), where the engine's HarfBuzz shaping never sees whole words.

shape(text)      -> same logical order, each letter replaced by its contextual presentation form,
                    lam-alef ligatures applied, harakat removed (marks cannot be positioned per character).
visual_line(t)   -> shape + reorder one line for left-to-right placement (RTL base, LTR runs kept intact).
"""
import re

# letter: (isolated, final, initial, medial); None where the form does not exist (right-joining letters)
FORMS = {
    'ء': ('ﺀ', None, None, None),
    'آ': ('ﺁ', 'ﺂ', None, None),
    'أ': ('ﺃ', 'ﺄ', None, None),
    'ؤ': ('ﺅ', 'ﺆ', None, None),
    'إ': ('ﺇ', 'ﺈ', None, None),
    'ئ': ('ﺉ', 'ﺊ', 'ﺋ', 'ﺌ'),
    'ا': ('ﺍ', 'ﺎ', None, None),
    'ب': ('ﺏ', 'ﺐ', 'ﺑ', 'ﺒ'),
    'ة': ('ﺓ', 'ﺔ', None, None),
    'ت': ('ﺕ', 'ﺖ', 'ﺗ', 'ﺘ'),
    'ث': ('ﺙ', 'ﺚ', 'ﺛ', 'ﺜ'),
    'ج': ('ﺝ', 'ﺞ', 'ﺟ', 'ﺠ'),
    'ح': ('ﺡ', 'ﺢ', 'ﺣ', 'ﺤ'),
    'خ': ('ﺥ', 'ﺦ', 'ﺧ', 'ﺨ'),
    'د': ('ﺩ', 'ﺪ', None, None),
    'ذ': ('ﺫ', 'ﺬ', None, None),
    'ر': ('ﺭ', 'ﺮ', None, None),
    'ز': ('ﺯ', 'ﺰ', None, None),
    'س': ('ﺱ', 'ﺲ', 'ﺳ', 'ﺴ'),
    'ش': ('ﺵ', 'ﺶ', 'ﺷ', 'ﺸ'),
    'ص': ('ﺹ', 'ﺺ', 'ﺻ', 'ﺼ'),
    'ض': ('ﺽ', 'ﺾ', 'ﺿ', 'ﻀ'),
    'ط': ('ﻁ', 'ﻂ', 'ﻃ', 'ﻄ'),
    'ظ': ('ﻅ', 'ﻆ', 'ﻇ', 'ﻈ'),
    'ع': ('ﻉ', 'ﻊ', 'ﻋ', 'ﻌ'),
    'غ': ('ﻍ', 'ﻎ', 'ﻏ', 'ﻐ'),
    'ـ': ('ـ', 'ـ', 'ـ', 'ـ'),
    'ف': ('ﻑ', 'ﻒ', 'ﻓ', 'ﻔ'),
    'ق': ('ﻕ', 'ﻖ', 'ﻗ', 'ﻘ'),
    'ك': ('ﻙ', 'ﻚ', 'ﻛ', 'ﻜ'),
    'ل': ('ﻝ', 'ﻞ', 'ﻟ', 'ﻠ'),
    'م': ('ﻡ', 'ﻢ', 'ﻣ', 'ﻤ'),
    'ن': ('ﻥ', 'ﻦ', 'ﻧ', 'ﻨ'),
    'ه': ('ﻩ', 'ﻪ', 'ﻫ', 'ﻬ'),
    'و': ('ﻭ', 'ﻮ', None, None),
    'ى': ('ﻯ', 'ﻰ', None, None),
    'ي': ('ﻱ', 'ﻲ', 'ﻳ', 'ﻴ'),
}
LAM_ALEF = {'آ': ('ﻵ', 'ﻶ'), 'أ': ('ﻷ', 'ﻸ'),
            'إ': ('ﻹ', 'ﻺ'), 'ا': ('ﻻ', 'ﻼ')}
HARAKAT = re.compile('[ً-ْٰٓ-ٕ]')
MIRROR = {'(': ')', ')': '(', '[': ']', ']': '[', '{': '}', '}': '{', '«': '»', '»': '«', '<': '>', '>': '<'}


def joins_left(c):   # can connect to the following letter
    f = FORMS.get(c)
    return bool(f and f[2])


def is_letter(c):
    return c in FORMS


def shape(text):
    t = HARAKAT.sub('', text)
    out = []
    i = 0
    n = len(t)
    while i < n:
        c = t[i]
        if c not in FORMS:
            out.append(c); i += 1; continue
        prev = t[i - 1] if i > 0 else ''
        connect_prev = is_letter(prev) and joins_left(prev)
        if c == 'ل' and i + 1 < n and t[i + 1] in LAM_ALEF:
            iso, fin = LAM_ALEF[t[i + 1]]
            out.append(fin if connect_prev else iso)
            i += 2; continue
        if FORMS[c][1] is None:   # non-joining letter (hamza)
            connect_prev = False
        nxt = t[i + 1] if i + 1 < n else ''
        connect_next = joins_left(c) and is_letter(nxt)
        iso, fin, ini, med = FORMS[c]
        if connect_prev and connect_next: out.append(med)
        elif connect_prev: out.append(fin)
        elif connect_next: out.append(ini)
        else: out.append(iso)
        i += 1
    return ''.join(out)


# Tokens that must stay intact and keep left-to-right order: rich-text tags, {placeholders},
# Latin words / numbers (with internal punctuation such as 1.01 or B33).
TOKEN = re.compile(r'<[^>]*>|\{[^}]*\}|[A-Za-z0-9][A-Za-z0-9.,:%\'_/+-]*[A-Za-z0-9%]|[A-Za-z0-9]')


def visual_line(line):
    """Reorder one shaped line so drawing characters left-to-right yields correct RTL display."""
    s = shape(line)
    parts = []
    pos = 0
    for m in TOKEN.finditer(s):
        if m.start() > pos: parts.append(('r', s[pos:m.start()]))
        parts.append(('l', m.group()))
        pos = m.end()
    if pos < len(s): parts.append(('r', s[pos:]))
    out = []
    for kind, seg in reversed(parts):
        if kind == 'l': out.append(seg)
        else: out.append(''.join(MIRROR.get(ch, ch) for ch in reversed(seg)))
    return ''.join(out)
