"""UE4.27 layout patches. Never touch FText or animation data.

Native text uses automatic BiDi; the separate pre-shaped animated renderer is
left alone. Bounded native text wraps instead of using CommonUI's LTR marquee.
"""
import struct
import props
from uasset import Package
from ui_audit import ref, value

TEXT_CLASSES = {'TextBlock', 'RichTextBlock', 'CommonTextBlock', 'CommonRichTextBlock'}
DIALOGUE = 'QueensDomain/Content/UI/DialogueSystem/'


def prop(name, typ, **kw):
    return props.Prop(name, typ, idx=0, **kw)


def number(name, v):
    return prop(name, 'FloatProperty', raw=struct.pack('<f', v))


def boolean(name, v):
    return prop(name, 'BoolProperty', bval=int(v), raw=b'')


def enum(name, typ, v, byte=False):
    return prop(name, 'ByteProperty' if byte else 'EnumProperty', enum=typ, nameval=v)


def structprop(name, typ, children):
    return prop(name, 'StructProperty', struct=typ, sguid=b'\0' * 16, children=children)


def vector(name, x, y):
    return prop(name, 'StructProperty', struct='Vector2D', sguid=b'\0' * 16,
                raw=struct.pack('<ff', x, y))


def margin(name, left=0, top=0, right=0, bottom=0):
    return structprop(name, 'Margin', [number(n, v) for n, v in
                      zip(('Left', 'Top', 'Right', 'Bottom'), (left, top, right, bottom))])


def setprop(ps, p):
    for i, old in enumerate(ps):
        if old.name == p.name:
            ps[i] = p
            return
    ps.append(p)


def shaping(ps, flow):
    # Preserve any unrelated options on an existing shaped-text struct.
    old = props.find(ps, 'ShapedTextOptions')
    children = list(old.children) if old else []
    for p in [boolean('bOverride_TextFlowDirection', True),
              enum('TextFlowDirection', 'ETextFlowDirection', 'ETextFlowDirection::' + flow),
              boolean('bOverride_TextShapingMethod', True),
              enum('TextShapingMethod', 'ETextShapingMethod', 'ETextShapingMethod::FullShaping')]:
        setprop(children, p)
    setprop(ps, structprop('ShapedTextOptions', 'ShapedTextOptions', children))


def wrapping(ps):
    setprop(ps, boolean('AutoWrapText', True))
    setprop(ps, number('WrapTextAt', 0))
    setprop(ps, number('MinDesiredWidth', 0))
    setprop(ps, enum('WrappingPolicy', 'ETextWrappingPolicy',
                     'ETextWrappingPolicy::AllowPerCharacterWrapping'))


def justify(ps, side):
    setprop(ps, enum('Justification', 'ETextJustify', 'ETextJustify::' + side, byte=True))


def flow(ps, direction='Culture'):
    setprop(ps, enum('FlowDirectionPreference', 'EFlowDirectionPreference',
                     'EFlowDirectionPreference::' + direction))


def objectprop(name, index):
    return prop(name, 'ObjectProperty', raw=struct.pack('<i', index))


def objectarray(name, indices):
    return prop(name, 'ArrayProperty', inner='ObjectProperty',
                raw=struct.pack('<i', len(indices)) + struct.pack('<%di' % len(indices), *indices))


def patch_package(path, a, x):
    pk = Package(a, x)
    changes = []
    choice = path in (DIALOGUE + 'DialogueOptionEntry', DIALOGUE + 'DialogueExitButton')
    screen = path == DIALOGUE + 'DialogueScreen'
    inventory = path.endswith('/StatusMenu/ItemDisplay')
    attributes = path.endswith('/StatusMenu/PlayerAttributes')
    equipment = path.endswith('/StatusMenu/EquipDisplay')
    hints = path.endswith('/Input/MenuButtonHintsWidget')
    hint = path.endswith('/Input/MenuButtonHintWidget')
    if inventory:
        # Fail closed if a later game build changes this cooked hierarchy.
        expected = {10: 'CanvasPanel', 12: 'CanvasPanelSlot', 15: 'CommonTextBlock',
                    18: 'HorizontalBox', 19: 'HorizontalBoxSlot', 20: 'HorizontalBoxSlot',
                    21: 'HorizontalBoxSlot', 24: 'Spacer'}
        for index, expected_class in expected.items():
            assert ref(pk, pk.exports[index - 1][0]) == expected_class, (path, index, 'unsupported hierarchy')
        assert ref(pk, 15) == 'Count' and ref(pk, 17) == 'Itemname'
        # Give visible quantities a consistent width (one through three digits).
        # Preserve the game's collapsed-count behavior for non-stackable equipment.
        # Reuse the now-unused Spacer and canvas slot; no new exports or bindings.
        pk.names = [{'Spacer': 'SizeBox', 'Default__Spacer': 'Default__SizeBox'}.get(n, n)
                    for n in pk.names]
        umg = pk.find_import('/Script/UMG')
        slot_class = pk.add_import('/Script/CoreUObject', 'Class', umg, 'SizeBoxSlot')
        slot_template = pk.add_import('/Script/UMG', 'SizeBoxSlot', umg, 'Default__SizeBoxSlot')
        slot = pk.exports[11]
        replacements = {slot[0]: slot_class, slot[2]: slot_template}
        start = slot[16]
        for dep in range(start, start + sum(slot[17:21])):
            pk.preload[dep] = replacements.get(pk.preload[dep], pk.preload[dep])
        slot[0], slot[2] = slot_class, slot_template
        changes.append(dict(export=0, name='QuantityColumn', cls='SizeBox',
                            reason=['reuse spacer and orphan slot for consistent visible quantity width'],
                            before={'class': 'Spacer'}, after={'class': 'SizeBox', 'slot': 'SizeBoxSlot'}))
    if hints:
        assert ref(pk, 8) == 'HintContainer' and ref(pk, pk.exports[7][0]) == 'HorizontalBox'
        # This blueprint only calls AddChildToHorizontalBox and discards its result.
        # Both panel APIs have the same signature. Keep field offsets and bytecode,
        # but update the reflected class, slot and function references together.
        renames = {'HorizontalBox': 'WrapBox', 'HorizontalBoxSlot': 'WrapBoxSlot',
                   'Default__HorizontalBox': 'Default__WrapBox',
                   'Default__HorizontalBoxSlot': 'Default__WrapBoxSlot',
                   'AddChildToHorizontalBox': 'AddChildToWrapBox'}
        pk.names = [renames.get(n, n) for n in pk.names]
        changes.append(dict(export=0, name='HintContainer', cls='WrapBox',
                            reason=['culture-aware wrapping panel; matching reflected AddChild API'],
                            before=renames, after={n: n for n in renames.values()}))
    for i, e in enumerate(pk.exports):
        cls, name = ref(pk, e[0]), ref(pk, i + 1)
        if cls not in TEXT_CLASSES | {'FB_AnimRichTextBlock', 'CanvasPanelSlot',
                                     'OverlaySlot', 'BorderSlot', 'ScrollBoxSlot', 'WidgetSwitcherSlot', 'SizeBox', 'SizeBoxSlot',
                                     'HorizontalBox', 'HorizontalBoxSlot', 'VerticalBoxSlot',
                                     'CanvasPanel', 'WidgetTree', 'WrapBox', 'WrapBoxSlot'}:
            continue
        data = pk.export_data(i)
        ps, end = props.Reader(pk, data).props(0)
        before = {p.name: value(pk, p) for p in ps}
        content = props.find(ps, 'Content')
        content_index = struct.unpack('<i', content.raw)[0] if content else 0
        content_class = ref(pk, pk.exports[content_index - 1][0]) if content_index > 0 else None
        reason = []
        scroll = props.find(ps, 'ScrollStyle')
        if cls in TEXT_CLASSES and scroll and scroll.raw != b'\0' * 4:
            shaping(ps, 'Auto')
            wrapping(ps)
            setprop(ps, objectprop('ScrollStyle', 0))
            if before.get('Justification') != 'ETextJustify::Center':
                justify(ps, 'Left')
            reason.append('replace LTR marquee with bounded native BiDi wrapping')
        if cls in TEXT_CLASSES and props.find(ps, 'AutoWrapText') and props.find(ps, 'AutoWrapText').bval:
            setprop(ps, enum('WrappingPolicy', 'ETextWrappingPolicy',
                             'ETextWrappingPolicy::AllowPerCharacterWrapping'))
            reason.append('wrap overlong tokens inside existing wrapped text')
            # A centered title/button remains centered. Ordinary Arabic prose uses
            # Slate's automatic paragraph direction and visual right justification.
            if before.get('Justification') != 'ETextJustify::Center':
                justify(ps, 'Left')
        if path.endswith('/Widgets/FS_DescriptionText') and name == 'MainTextBlock':
            shaping(ps, 'Auto')
            # Slate flips Left/Right justification for RTL paragraph base direction.
            # Logical Left is the leading edge: visually right for Arabic, left for English.
            justify(ps, 'Left')
            setprop(ps, margin('Margin', 6, 4, 6, 4))
            reason.append('right-aligned native BiDi descriptions with internal padding')
        if path.endswith('/Journal/JournalEntry') and cls == 'OverlaySlot' and content_class == 'HorizontalBox':
            setprop(ps, enum('HorizontalAlignment', 'EHorizontalAlignment', 'HAlign_Fill', byte=True))
            reason.append('give journal/guide rows the full selection width instead of natural text width')
        if '/Journal/' in path and name == 'NoteTitleText':
            shaping(ps, 'Auto')
            justify(ps, 'Left')
            setprop(ps, objectprop('ScrollStyle', 0))
            reason.append('native leading-edge note title; avoid scrolling short Arabic headings from mid-text')
        if choice:
            if cls in TEXT_CLASSES:
                shaping(ps, 'Auto')
                wrapping(ps)
                setprop(ps, prop('ScrollStyle', 'ObjectProperty', raw=b'\0' * 4))
                setprop(ps, enum('Justification', 'ETextJustify', 'ETextJustify::Center', byte=True))
                setprop(ps, margin('Margin', 0, 0, 0, 6))
                reason.append('center and wrap choice, without a horizontal marquee')
            if cls == 'CanvasPanelSlot' and content_class in TEXT_CLASSES:
                setprop(ps, structprop('LayoutData', 'AnchorData', [
                    margin('Offsets', 30, 6, 20, 0),
                    structprop('Anchors', 'Anchors', [vector('Minimum', 0, 0), vector('Maximum', 1, 0)]),
                    vector('Alignment', 0, 0)]))
                setprop(ps, boolean('bAutoSize', True))
                reason.append('replace 950-unit fixed width with parent width; grow height with text')
            if cls == 'SizeBox':
                setprop(ps, boolean('bOverride_HeightOverride', False))
                setprop(ps, boolean('bOverride_MinDesiredHeight', True))
                setprop(ps, number('MinDesiredHeight', 50))
                reason.append('50-unit minimum instead of fixed choice height')
        if screen:
            if name == 'DialogueSequenceText':
                # Leave pre-shaped strings and FB renderer direction/reveal untouched.
                wrapping(ps)
                justify(ps, 'Left')
                reason.append('remove 980-unit minimum/explicit wrap from 878-unit dialogue box')
            if name == 'Greeting':
                wrapping(ps)
                justify(ps, 'Left')
                reason.append('wrap greeting inside choices viewport')
            if cls in ('OverlaySlot', 'ScrollBoxSlot', 'VerticalBoxSlot', 'WidgetSwitcherSlot') and content_class in ('VerticalBox', 'Overlay', 'WidgetSwitcher'):
                setprop(ps, enum('HorizontalAlignment', 'EHorizontalAlignment', 'HAlign_Fill', byte=True))
                reason.append('propagate allocated scroll viewport width to dialogue content')
            if cls == 'OverlaySlot' and before.get('Content') == 'DialogueSequenceText':
                setprop(ps, margin('Padding', 20, 0, 20, 6))
                reason.append('symmetric horizontal inset and nonnegative top padding')
            if name == 'NPCName':
                justify(ps, 'Left')
                reason.append('right-aligned speaker name')
            if cls == 'CanvasPanelSlot' and before.get('Content') == 'NPCNameBox':
                layout = props.find(ps, 'LayoutData').children
                setprop(layout, structprop('Anchors', 'Anchors',
                        [vector('Minimum', 1, 0), vector('Maximum', 1, 0)]))
                setprop(layout, vector('Alignment', 1, 1))
                reason.append('dock speaker name to dialogue right edge with width-aware pivot')
        if attributes:
            if cls == 'HorizontalBox':
                flow(ps)
                reason.append('culture-aware label/value column order; no graphic mirroring')
            if cls in TEXT_CLASSES:
                is_label = name.endswith('Label') or name == 'Status'
                shaping(ps, 'LeftToRight')
                justify(ps, 'Right' if is_label else 'Left')
                flow(ps, 'LeftToRight')
                reason.append('separate Arabic label alignment from LTR numeric formatting')
        if inventory:
            # Reuse existing objects/slots: the canvas becomes the icon group inside
            # the row's existing HBox. Its icon/quick/equipped overlays stay together.
            if cls == 'WidgetTree':
                setprop(ps, objectprop('RootWidget', 18))
            elif i + 1 == 18:
                ps = [p for p in ps if p.name != 'Slot']
                flow(ps)
            elif i + 1 == 10:
                setprop(ps, objectarray('Slots', [11, 13, 14]))
                setprop(ps, objectprop('Slot', 19))
                flow(ps, 'LeftToRight')
            elif i + 1 == 19:
                setprop(ps, objectprop('Content', 10))
                setprop(ps, structprop('Size', 'SlateChildSize', [number('Value', 1),
                        enum('SizeRule', 'ESlateSizeRule', 'ESlateSizeRule::Automatic', byte=True)]))
                setprop(ps, margin('Padding', 8, 0, 8, 0))
            elif i + 1 == 12:
                ps = [objectprop('Parent', 24), objectprop('Content', 15),
                      enum('HorizontalAlignment', 'EHorizontalAlignment', 'HAlign_Fill', byte=True),
                      enum('VerticalAlignment', 'EVerticalAlignment', 'VAlign_Center', byte=True)]
            elif i + 1 == 21:
                setprop(ps, objectprop('Content', 24))
            elif i + 1 == 24:
                ps = [number('WidthOverride', 45), boolean('bOverride_WidthOverride', True),
                      objectarray('Slots', [12]), objectprop('Slot', 21)]
            elif i + 1 == 20:
                setprop(ps, enum('HorizontalAlignment', 'EHorizontalAlignment', 'HAlign_Fill', byte=True))
                setprop(ps, enum('VerticalAlignment', 'EVerticalAlignment', 'VAlign_Center', byte=True))
            if name == 'Itemname':
                justify(ps, 'Right')
                flow(ps, 'LeftToRight')
            if name == 'Count':
                setprop(ps, objectprop('Slot', 12))
                shaping(ps, 'LeftToRight')
                justify(ps, 'Left')
                flow(ps, 'LeftToRight')
            reason.append('responsive name/icon/quantity row; preserve icon overlays and object identities')
        if equipment and name in ('Itemname', 'Unequipped'):
            shaping(ps, 'Auto')
            justify(ps, 'Left')
            reason.append('equipment names aligned within their existing text column')
        if equipment and cls == 'CanvasPanelSlot' and before.get('Content') == 'UnequippedText':
            layout = props.find(ps, 'LayoutData').children
            setprop(layout, structprop('Anchors', 'Anchors',
                    [vector('Minimum', 0, .5), vector('Maximum', 1, .5)]))
            setprop(props.find(layout, 'Offsets').children, number('Right', 10))
            reason.append('empty equipment label spans the same name column as equipped items')
        if equipment and cls == 'BorderSlot' and before.get('Content') == 'Unequipped':
            setprop(ps, enum('HorizontalAlignment', 'EHorizontalAlignment', 'HAlign_Fill', byte=True))
        if path.endswith('/SaveMenu/SaveSlotWidget'):
            if cls == 'SizeBox' and before.get('MaxDesiredWidth') == 110.30277252197266:
                setprop(ps, boolean('bOverride_MaxDesiredWidth', False))
                reason.append('allow save-date label its natural width beside the numeric date')
            if name == 'SavedLabel':
                setprop(ps, prop('ScrollStyle', 'ObjectProperty', raw=b'\0' * 4))
                reason.append('save-date label fits natural-width box without marquee clipping')
        if equipment and cls == 'VerticalBoxSlot' and before.get('Content') == 'WeaponLevelBox':
            setprop(ps, enum('HorizontalAlignment', 'EHorizontalAlignment', 'HAlign_Right', byte=True))
            reason.append('align equipment level and meter with item name; keep meter direction')
        if hint:
            if cls == 'HorizontalBox':
                flow(ps)
                reason.append('keep button icon and label grouped in culture reading order')
            if cls == 'HorizontalBoxSlot' and before.get('Content') == 'InputViewIcon':
                setprop(ps, margin('Padding', 8, 0, 6, 0))
                reason.append('replace negative icon spacing with a positive gap')
        if hints:
            if cls == 'WidgetTree':
                setprop(ps, objectprop('RootWidget', 8))
            if name == 'HintContainer':
                ps = [p for p in ps if p.name != 'Slot']
                setprop(ps, boolean('bExplicitWrapSize', False))
                setprop(ps, vector('InnerSlotPadding', 12, 6))
                flow(ps)
                reason.append('wrap whole action groups using allocated width')
        if cls == 'CanvasPanelSlot' and content_class == 'MenuButtonHintsWidget_C':
            layout = props.find(ps, 'LayoutData').children
            offs = props.find(layout, 'Offsets').children
            # Leave room for the existing coin panel in shop/inventory footers.
            left = 220 if '/Shop/' in path or '/Menus/' in path else 24
            setprop(offs, number('Left', left))
            setprop(offs, number('Right', 24))
            setprop(layout, structprop('Anchors', 'Anchors',
                    [vector('Minimum', 0, 1), vector('Maximum', 1, 1)]))
            setprop(layout, vector('Alignment', 0, 1))
            setprop(ps, boolean('bAutoSize', True))
            reason.append('footer safe insets; stretch horizontally and grow wrapped hints upward')
        if path.endswith('/HUD/FS_PlayerHUD'):
            if name == 'InteractText':
                wrapping(ps)
                reason.append('wrap interactive prompts without reducing font size')
            if cls == 'CanvasPanelSlot' and before.get('Content') == 'InteractText':
                layout = props.find(ps, 'LayoutData').children
                setprop(layout, structprop('Anchors', 'Anchors',
                        [vector('Minimum', .25, .5), vector('Maximum', .75, .5)]))
                setprop(layout, margin('Offsets', 8, 40, 8, 0))
                setprop(layout, vector('Alignment', 0, 0))
                setprop(ps, boolean('bAutoSize', True))
                reason.append('responsive central prompt width replaces fixed 200-unit slot')
        after = {p.name: value(pk, p) for p in ps}
        if before != after:
            changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
            changes.append(dict(export=i+1, name=name, cls=cls, reason=reason,
                                before={k: before.get(k) for k in changed},
                                after={k: after.get(k) for k in changed}))
            pk.replace_export(i, props.Writer(pk).props(ps) + data[end:])
    import rtl_layout
    changes.extend(rtl_layout.apply(path, pk))
    return (*pk.build(), changes) if changes else (a, x, [])


def apply(pk_src, files):
    """Compose with already-patched exports, so fade timing survives layout edits."""
    report = {}
    for asset in sorted(pk_src.files):
        if not asset.endswith('.uasset') or not asset.startswith('QueensDomain/Content/'):
            continue
        path = asset[:-7]
        a = files.get(asset)
        if a is None:
            a = pk_src.read(asset)
        binding_group = path.endswith(('/OptionsMenu_BindingEntry_Group','/OptionsMenu_AxisBindingEntry_Group'))
        if b'WidgetBlueprintGeneratedClass' not in a or (not binding_group and not any(c.encode() in a for c in TEXT_CLASSES)):
            continue
        # References to widgets also occur in actors. Only edit actual widget packages.
        x = files.get(path + '.uexp')
        if x is None:
            x = pk_src.read(path + '.uexp')
        pk = Package(a, x)
        if not any(ref(pk, e[0]) == 'WidgetBlueprintGeneratedClass' for e in pk.exports):
            continue
        a, x, changes = patch_package(path, a, x)
        if changes:
            files[asset], files[path + '.uexp'] = a, x
            report[path] = changes
    return report
