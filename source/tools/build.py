"""Build the Arabic patch pak for Queen's Domain.
Usage: py -I tools/build.py <original_pak> <out_pak> [--mirror] [--allow-missing]"""
import sys, os, json, struct, glob
sys.path.insert(0, os.path.dirname(__file__))
import uasset, props, locres, pakwrite, arshape, measure, re, ui_layout
from pak import Pak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACE_PKG = '/Game/UI/Fonts/AR_NotoNaskhArabicUI'
FACE_OBJ = 'AR_NotoNaskhArabicUI'
FONT_TTF = os.path.join(ROOT, 'assets', 'fonts', 'NotoNaskhArabicUI-Regular.ttf')
AR_RANGES = [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)]
SCALE = float(os.environ.get('AR_SCALE', '1.15'))
# Arabic culture code. ar-MA uses Western digits by default; plain "ar" makes the game format its
# save-file names with Arabic-Indic digits (System٠.sav) and lose the player's existing saves.
AR_CULTURE = os.environ.get('AR_CULTURE', 'ar-MA')
COMPOSITES = ['QueensDomain/Content/UI/UI_Style/FontStyles/Rockwell',
              'QueensDomain/Content/UI/Fonts/CodecCold',
              'QueensDomain/Content/UI/UI_Style/FontStyles/Silver_Font',
              'QueensDomain/Content/UI/UI_Style/FontStyles/Silver_Font_Bmb']


def P(name, typ, **kw):
    t = props.Prop(name, typ, idx=0)
    t.__dict__.update(kw)
    return t


def make_face(pk_src):
    """Clone the game's Codec-Pro-News FontFace asset as a new package pointing at our .ufont."""
    a = pk_src.read('QueensDomain/Content/UI/Fonts/Codec-Pro-News.uasset')
    x = pk_src.read('QueensDomain/Content/UI/Fonts/Codec-Pro-News.uexp')
    pk = uasset.Package(a, x)
    ren = {'/Game/UI/Fonts/Codec-Pro-News': FACE_PKG, 'Codec-Pro-News': FACE_OBJ}
    pk.names = [ren.get(n, n) for n in pk.names]
    return pk.build()


def range_item(lo, hi):
    def bound(name, v):
        return P(name, 'StructProperty', struct='Int32RangeBound', sguid=b'\0' * 16, children=[
            P('Type', 'ByteProperty', enum='ERangeBoundTypes', nameval='ERangeBoundTypes::Inclusive'),
            P('Value', 'IntProperty', raw=struct.pack('<i', v))])
    return [bound('LowerBound', lo), bound('UpperBound', hi)]


def patch_composite(pk_src, path):
    a = pk_src.read(path + '.uasset')
    x = pk_src.read(path + '.uexp')
    pk = uasset.Package(a, x)
    lst, end = props.Reader(pk, x).props(0)
    tail = x[end:]
    pkg_imp = pk.add_import('/Script/CoreUObject', 'Package', 0, FACE_PKG)
    face_imp = pk.add_import('/Script/Engine', 'FontFace', pkg_imp, FACE_OBJ)
    ex = pk.exports[0]
    sbs, cbs = ex[17], ex[18]
    pk.preload.insert(sbs + cbs, face_imp)  # create-before-serialization, like the other faces
    ex[18] = cbs + 1
    cf = props.find(lst, 'CompositeFont')
    sub = [
        P('CharacterRanges', 'ArrayProperty', inner='StructProperty',
          itag=P('CharacterRanges', 'StructProperty', struct='Int32Range', sguid=b'\0' * 16),
          items=[range_item(lo, hi) for lo, hi in AR_RANGES]),
        P('Typeface', 'StructProperty', struct='Typeface', sguid=b'\0' * 16, children=[
            P('Fonts', 'ArrayProperty', inner='StructProperty',
              itag=P('Fonts', 'StructProperty', struct='TypefaceEntry', sguid=b'\0' * 16),
              items=[[P('Name', 'NameProperty', nameval='Regular'),
                      P('Font', 'StructProperty', struct='FontData', sguid=b'\0' * 16,
                        raw=struct.pack('<Iii', 1, face_imp, 0))]])]),
        P('ScalingFactor', 'FloatProperty', raw=struct.pack('<f', SCALE)),
    ]
    st = props.find(cf.children, 'SubTypefaces')
    if st is None:
        st = P('SubTypefaces', 'ArrayProperty', inner='StructProperty',
               itag=P('SubTypefaces', 'StructProperty', struct='CompositeSubFont', sguid=b'\0' * 16), items=[])
        cf.children.append(st)
    st.items.insert(0, sub)
    return pk.build(props.Writer(pk).props(lst) + tail)


def patch_languages(pk_src):
    path = 'QueensDomain/Content/Player/PlayerBalance'
    a = pk_src.read(path + '.uasset')
    x = pk_src.read(path + '.uexp')
    pk = uasset.Package(a, x)
    lst, end = props.Reader(pk, x).props(0)
    t = props.find(lst, 'SupportedLanguages')
    n, = struct.unpack_from('<i', t.raw, 0)
    if b'\x03\0\0\0ar\0' not in t.raw:
        t.raw = struct.pack('<i', n + 1) + t.raw[4:] + locres.wstr(AR_CULTURE)
    return pk.build(props.Writer(pk).props(lst) + x[end:])


def patch_locmeta(pk_src):
    d = pk_src.read('QueensDomain/Content/Localization/Game/Game.locmeta')
    p = 17
    for _ in range(2):
        n, = struct.unpack_from('<i', d, p)
        p += 4 + n
    cnt, = struct.unpack_from('<i', d, p)
    return d[:p] + struct.pack('<i', cnt + 1) + d[p + 4:] + locres.wstr(AR_CULTURE)


# Screen headers use a scrolling text widget that mis-positions right-to-left paragraphs (text is pushed
# off the right edge). A leading LEFT-TO-RIGHT MARK gives those single-line Arabic headers an LTR base
# direction; the Arabic letters themselves are still shaped and ordered right-to-left by the engine.
# Applied only to the built display file; the translation sources stay untouched.
LRM_KEYS = {'ImportedStringTable::' + k for k in (
    'options_title', 'options_video_title', 'options_audio_title', 'options_gameplay_title',
    'options_controls_title', 'options_bindings_title', 'journal_title', 'pausemenu_title',
    'teleport_title', 'titlescreen_fileselecttitle', 'photomode_name', 'menu_options')}


# Strings drawn by FB_AnimRichTextBlock (dialogue, intro, endings, ritual): that widget places characters
# one at a time, so Arabic must be pre-shaped (and, depending on ANIM_MODE, visually reordered).
ANIM_RE = re.compile(r'^(ImportedStringTable::(d_(?!umbada_buy_option|umbada_sell_option|sipeha_endchoice).*'
                     r'|intro_line_\d+|end\dtext_\d+|postend_awaken_\d+|ritualtext_\d+|queen_talk_\d+|queen_break_\d+'
                     r'|ros_dragon_talk_\d+)|Dialogue::.*)$')
ANIM_MODE = os.environ.get('ANIM_MODE', 'visual')
# (wrap width in Slate units, font size) of the widget each string is shown in; read from the widget assets.
DIALOGUE_BOX = (860.0, 22)      # DialogueScreen: WrapTextAt 980 but the box allocates ~870 units in game (measured)
CINEMATIC_BOX = (1300.0, 33)    # Intro/Ending/Awaken/Ritual text: WrapTextAt 1300, BigDialogueRichText size 33
WRAP_SAFETY = 0.93


def anim_box(key):
    k = key.split('::', 1)[1]
    if re.match(r'(intro_line|end\dtext|postend_awaken|ritualtext)_', k):
        return CINEMATIC_BOX
    return DIALOGUE_BOX


def wrap_logical(par, width, size):
    words = par.split(' ')
    lines, cur = [], ''
    for w in words:
        cand = w if not cur else cur + ' ' + w
        if cur and measure.width(arshape.shape(cand), size) > width:
            lines.append(cur); cur = w
        else:
            cur = cand
    lines.append(cur)
    return lines


def anim_display(key, text):
    if ANIM_MODE in ('shape', 'rtlflow'):
        return arshape.shape(text)
    width, size = anim_box(key)
    width *= WRAP_SAFETY
    out = []
    for raw in text.split(NL):
        cr = raw.endswith(CR)
        par = raw[:-1] if cr else raw
        vis = NL.join(arshape.visual_line(l) for l in wrap_logical(par, width, size)) if par else ''
        out.append(vis + (CR if cr else ''))
    return NL.join(out)


NL, CR = chr(10), chr(13)

# Animated-text widgets: the FB_AnimRichTextBlock export inside each and the string keys it shows.
ANIM_WIDGETS = {
    'QueensDomain/Content/RuinsLevel/Intro/IntroTextWidget': ['RichText'],
    'QueensDomain/Content/UI/DialogueSystem/DialogueScreen': ['DialogueSequenceText'],
    'QueensDomain/Content/Cutscenes/EndingTextWidget': ['RichText'],
    'QueensDomain/Content/Cutscenes/AwakenTextWidget': ['RichText'],
    'QueensDomain/Content/Cutscenes/RitualCutscene/RitualText': ['RichText', 'EatTex'],
}


def patch_widget_print(pk_src, path, export_names, speed):
    """Set TextPrintSpeed (delay between letters) on the given FB_AnimRichTextBlock exports."""
    a = pk_src.read(path + '.uasset'); x = pk_src.read(path + '.uexp')
    pk = uasset.Package(a, x)
    for i, e in enumerate(pk.exports):
        if pk.fname(e[4]) not in export_names:
            continue
        data = pk.export_data(i)
        lst, end = props.Reader(pk, data).props(0)
        lst = [t for t in lst if t.name != 'TextPrintSpeed']
        lst.insert(0, P('TextPrintSpeed', 'FloatProperty', raw=struct.pack('<f', speed)))
        pk.replace_export(i, props.Writer(pk).props(lst) + data[end:])
    return pk.build()


def patch_widget_flow(pk_src, path, export_names):
    """Force ShapedTextOptions.TextFlowDirection = RightToLeft on the given widget exports."""
    a = pk_src.read(path + '.uasset'); x = pk_src.read(path + '.uexp')
    pk = uasset.Package(a, x)
    for i, e in enumerate(pk.exports):
        if pk.fname(e[4]) not in export_names:
            continue
        data = pk.export_data(i)
        lst, end = props.Reader(pk, data).props(0)
        lst = [t for t in lst if t.name != 'ShapedTextOptions']
        lst.append(P('ShapedTextOptions', 'StructProperty', struct='ShapedTextOptions', sguid=b'\0' * 16, children=[
            P('bOverride_TextFlowDirection', 'BoolProperty', bval=1, raw=b''),
            P('TextFlowDirection', 'EnumProperty', enum='ETextFlowDirection', nameval='ETextFlowDirection::RightToLeft')]))
        pk.replace_export(i, props.Writer(pk).props(lst) + data[end:])
    return pk.build()


def load_translations():
    tr = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'translations', '*.json'))):
        for k, v in json.load(open(f, encoding='utf-8')).items():
            tr[k] = v
    return tr


def build_locres(allow_missing):
    inv = json.load(open(os.path.join(ROOT, 'work', 'inventory.json'), encoding='utf-8'))
    tr = load_translations()
    missing, ents = [], []
    for x in inv:
        t = tr.get(x['id'])
        if t is None:
            missing.append(x['id'])
            t = x['src']
        if ANIM_RE.match(x['id']):
            t = anim_display(x['id'], t)
        if x['id'] in LRM_KEYS and not t.startswith('‎'):
            t = '‎' + t
        ents.append((x['nshash'], x['ns'], x['keyhash'], x['key'], x['srchash'], t))
    if missing and not allow_missing:
        raise SystemExit('missing translations: %d (e.g. %s)' % (len(missing), missing[:5]))
    tmp = os.path.join(ROOT, 'work', '_ar.locres')
    locres.write(tmp, ents)
    return open(tmp, 'rb').read(), missing


def main():
    src, out = sys.argv[1], sys.argv[2]
    pk = Pak(src)
    measure.load_latin(pk)
    files = {}
    base = FACE_PKG.replace('/Game/', 'QueensDomain/Content/')
    files[base + '.uasset'], files[base + '.uexp'] = make_face(pk)
    files[base + '.ufont'] = open(FONT_TTF, 'rb').read()
    for c in COMPOSITES:
        files[c + '.uasset'], files[c + '.uexp'] = patch_composite(pk, c)
    files['QueensDomain/Content/Player/PlayerBalance.uasset'], files['QueensDomain/Content/Player/PlayerBalance.uexp'] = patch_languages(pk)
    files['QueensDomain/Content/Localization/Game/Game.locmeta'] = patch_locmeta(pk)
    loc, missing = build_locres('--allow-missing' in sys.argv)
    files['QueensDomain/Content/Localization/Game/%s/Game.locres' % AR_CULTURE] = loc
    # The plugin reveals letters in left-to-right placement order (native code); for Arabic that reads backwards.
    # Two variants: PRINT_SPEED=0 keeps the original letter timing and needs the exe patch (tools/exepatch.py)
    # that reverses the reveal inside Arabic runs; the default sets the delay to ~0 so each block fades in at once.
    speed = float(os.environ.get('PRINT_SPEED', '0.0001'))
    if speed > 0:
        for w, names in ANIM_WIDGETS.items():
            files[w + '.uasset'], files[w + '.uexp'] = patch_widget_print(pk, w, names, speed)
    if ANIM_MODE == 'rtlflow':
        for w, names in ANIM_WIDGETS.items():
            files[w + '.uasset'], files[w + '.uexp'] = patch_widget_flow(pk, w, names)
    if '--mirror' in sys.argv:
        ini = pk.read('QueensDomain/Config/DefaultEngine.ini').decode('utf-8-sig')
        ini = ini.rstrip() + '\r\n\r\n[SystemSettings]\r\nSlate.ShouldFollowCultureByDefault=1\r\n'
        files['QueensDomain/Config/DefaultEngine.ini'] = ini.encode('utf-8')
    layout_report = ui_layout.apply(pk, files)
    import currency_layout
    currency_layout.apply(files, layout_report)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    pakwrite.write(out, files)
    with open(out + '.layout.json', 'w', encoding='utf-8') as f:
        json.dump(layout_report, f, ensure_ascii=False, indent=2)
    print('layout:', len(layout_report), 'widget packages')
    print('built', out, len(files), 'files; untranslated:', len(missing))


if __name__ == '__main__':
    main()
