"""Explicit semantic rows for the supported 1.01.03 cooked UI.

Culture is applied to selected panels, never to the viewport or game controls.
New native panels retain the existing text objects and all blueprint bindings.
"""
import struct
import props
from ui_audit import ref, value


def apply(path, pk):
    from ui_layout import (setprop, objectprop, objectarray, enum, boolean, number,
                           vector, margin, structprop, flow, shaping, justify, wrapping,
                           TEXT_CLASSES)
    original_count = len(pk.exports)
    edits, before, tails = {}, {}, {}
    currency_menu=path.endswith(('/Shop/ShopMenu','/UpgradeMachine/WeaponUpgrade_UI','/Menus/GameMenu'))
    if currency_menu:
        # These three packages have exactly one ItemDisplay instance: CoinDisplay.
        # Retarget its class AND reflected property/function import references.
        old='/Game/UI/Menus/StatusMenu/ItemDisplay'
        names={old:old.replace('ItemDisplay','CurrencyDisplay'),
               'ItemDisplay_C':'CurrencyDisplay_C','Default__ItemDisplay_C':'Default__CurrencyDisplay_C'}
        pk.names=[names.get(n,n) for n in pk.names]

    def get(n):
        if n not in edits:
            data = pk.replaced.get(n-1, pk.export_data(n-1))
            ps, end = props.Reader(pk, data).props(0)
            edits[n], tails[n] = ps, data[end:]
            before[n] = {p.name: value(pk, p) for p in ps}
        return edits[n]

    def put(n, *ps):
        for p in ps: setprop(get(n), p)

    def ids(n):
        raw = props.find(get(n), 'Slots').raw
        return list(struct.unpack('<%di' % ((len(raw)-4)//4), raw[4:]))

    def childsize(fill=False):
        return structprop('Size', 'SlateChildSize', [number('Value', 1),
            enum('SizeRule', 'ESlateSizeRule', 'ESlateSizeRule::' + ('Fill' if fill else 'Automatic'), byte=True)])

    def native(n, numeric=False, wrap=False):
        ps = get(n)
        shaping(ps, 'LeftToRight' if numeric else 'Auto')
        flow(ps, 'LeftToRight')  # glyph/control coordinates separate from panel order
        justify(ps, 'Left')
        if ref(pk, pk.exports[n-1][0]) == 'CommonTextBlock': put(n, objectprop('ScrollStyle', 0))
        if wrap:
            wrapping(ps)
        else:
            # Natural-size numeric/short value boxes must measure their whole
            # string. Auto-wrap on those boxes feeds the previous desired width
            # back into the next frame and can split even a single Arabic word.
            put(n,boolean('AutoWrapText',False),number('WrapTextAt',0))

    def new(cls, name, outer, ps):
        template = next((e for e in pk.exports[:original_count] if ref(pk, e[0]) == cls),None)
        if template is None:
            fallback='CanvasPanelSlot' if cls.endswith('Slot') else 'CanvasPanel'
            template=list(next(e for e in pk.exports[:original_count] if ref(pk,e[0])==fallback))
            umg=pk.find_import('/Script/UMG')
            assert umg
            template[0]=pk.find_import(cls) or pk.add_import('/Script/CoreUObject','Class',umg,cls)
            template[2]=pk.find_import('Default__'+cls) or pk.add_import('/Script/UMG',cls,umg,'Default__'+cls)
        e = list(template)
        e[3], e[4], e[5] = outer, pk.name(name), 0
        e[7], e[8] = 0, len(pk.b) + len(pk.orig_uexp) + len(pk.exports)
        e[16:21] = [len(pk.preload), 0, 0, 2, 1]
        pk.preload.extend([e[0], e[2], outer])
        assert len(pk.depends_blob) == 4 * len(pk.exports)
        pk.depends_blob += b'\0' * 4
        pk.exports.append(e)
        n = len(pk.exports)
        edits[n], before[n], tails[n] = ps, {}, b'\0\0\0\0'  # UObject has no native payload
        return n

    tree = next(i+1 for i,e in enumerate(pk.exports) if ref(pk,e[0]) == 'WidgetTree')

    def row(name, children):
        n = new('HorizontalBox', name, tree, [])
        flow(get(n))
        slots = []
        for index, (child, fill) in enumerate(children):
            slot = new('HorizontalBoxSlot', name+'Slot'+str(index), n, [
                objectprop('Parent', n), objectprop('Content', child), childsize(fill),
                margin('Padding', 6, 0, 6, 0),
                enum('HorizontalAlignment','EHorizontalAlignment','HAlign_Fill',byte=True),
                enum('VerticalAlignment','EVerticalAlignment','VAlign_Center',byte=True)])
            put(child, objectprop('Slot', slot)); slots.append(slot)
        put(n, objectarray('Slots', slots))
        return n

    def canvas(parent, child, name, left, top, right, height, minx=0, maxx=1):
        n = new('CanvasPanelSlot', name, parent, [objectprop('Parent',parent),objectprop('Content',child),
            structprop('LayoutData','AnchorData', [margin('Offsets',left,top,right,height),
                structprop('Anchors','Anchors',[vector('Minimum',minx,0),vector('Maximum',maxx,0)]),
                vector('Alignment',0,0)])])
        put(child,objectprop('Slot',n))
        return n

    # Some frozen release headers contain an LRM. Preserve that compiled text,
    # and position its entire natural-width box through a culture-aware panel.
    # This also retains left-leading English headers without an RTL override.
    from build import LRM_KEYS
    for i,e in enumerate(pk.exports[:original_count]):
        if ref(pk,e[0])!='CanvasPanelSlot':continue
        slot=i+1; content=props.find(get(slot),'Content')
        if not content:continue
        child=struct.unpack('<i',content.raw)[0]
        if child<=0 or ref(pk,pk.exports[child-1][0]) not in TEXT_CLASSES:continue
        ps=get(child); name=ref(pk,child); tp=props.find(ps,'Text'); raw=tp.raw if tp else b''
        is_header=name=='Title' or any(key.split('::')[1].encode()+b'\0' in raw for key in LRM_KEYS)
        v={p.name:value(pk,p) for p in ps}
        if not is_header or v.get('Justification')=='ETextJustify::Center' or name.startswith('Confirm'):continue
        header=row('RTL_Header_'+str(child),[(child,False)])
        put(slot,objectprop('Content',header));put(header,objectprop('Slot',slot))
        put(ids(header)[0],childsize(True),margin('Padding',0,0,0,0),
            enum('HorizontalAlignment','EHorizontalAlignment','HAlign_Left',byte=True))
        native(child)
        put(child,boolean('AutoWrapText',False),number('MinDesiredWidth',0))

    for i, e in enumerate(pk.exports[:original_count]):
        n, cls, name = i+1, ref(pk,e[0]), ref(pk,i+1)
        if path.endswith('/Journal/EnemyDescriptionBox'):
            if cls == 'HorizontalBox': flow(get(n))
            if cls in TEXT_CLASSES:
                native(n, numeric=name in ('XPNum','HPNum','DamageNum','TotalKillCount'),wrap=name in ('Drop1','Drop2'))
                if name in ('SlashResistance','ImpactResistance','PierceResistance'):
                    put(n,number('WrapTextAt',160))
                if name.endswith('Label'):
                    slot=struct.unpack('<i',props.find(get(n),'Slot').raw)[0]
                    parent=struct.unpack('<i',props.find(get(slot),'Parent').raw)[0]
                    cap=props.find(get(parent),'MaxDesiredWidth')
                    if cap:put(n,boolean('AutoWrapText',False),number('WrapTextAt',struct.unpack('<f',cap.raw)[0]))
            if cls == 'VerticalBox' and name == 'VerticalBox_1': flow(get(n))
        if path.endswith(('/OptionsMenu/OptionsMenu_Entry','/OptionsMenu/OptionsMenu_BindingEntry')):
            if cls == 'HorizontalBox' and name == 'HorizontalBox_0': flow(get(n))
            if name == 'ControlWidget' or (name == 'SizeBox_0' and path.endswith('BindingEntry')):
                flow(get(n),'LeftToRight')
            if name == 'FieldLabel': native(n,wrap=True)
        if path.endswith(('/OptionsMenu/OptionsMenu_BindingEntry_Group','/OptionsMenu/OptionsMenu_AxisBindingEntry_Group')):
            if cls=='HorizontalBox' and name=='HorizontalBox_0':flow(get(n))
        if path.endswith('/Journal/JournalEntry'):
            if cls == 'HorizontalBox': flow(get(n))
            if name == 'Name': native(n,wrap=True)
            if name == 'Number': native(n,numeric=True)
        if path.endswith('/StatusMenu/ItemDisplay') and name == 'Itemname':
            native(n,wrap=True)
        if path.endswith(('/Journal/JournalMenu','/Challenges/Challenges_Menu')):
            if name in ('HorizontalBox','HorizontalBox_187') and cls == 'HorizontalBox': flow(get(n))
            if name.startswith('CompletionRatePercent'): native(n,numeric=True)
            completion_label = 'CommonTextBlock' if path.endswith('/Journal/JournalMenu') else 'CommonTextBlock_136'
            if name == completion_label and cls in TEXT_CLASSES:
                native(n)
            if cls == 'CanvasPanelSlot':
                v={p.name:value(pk,p) for p in get(n)}
                if v.get('Content') == 'MenuButtonHintsWidget':
                    layout=props.find(get(n),'LayoutData').children
                    setprop(props.find(layout,'Offsets').children,number('Left',950))
        if path.endswith('/StatusMenu/PlayerAttributes') and cls in TEXT_CLASSES:
            # Labels use native paragraph detection; numeric fields stay isolated.
            native(n, numeric=not(name.endswith('Label') or name == 'Status'))

    if path.endswith('/OptionsMenu/OptionsMenu_Entry'):
        # Allocate remaining width to the label instead of its redundant spacer.
        put(23,childsize(True),margin('Padding',14,2,14,0))
        put(24,childsize(False))
        put(26,boolean('bOverride_MaxDesiredWidth',False))
        put(28,enum('HorizontalAlignment','EHorizontalAlignment','HAlign_Fill',byte=True))
        # Keep the original label-only Shadow brush at the label's desired size.
        # Stretching Border_0 with the Fill slot produces the reported black bar.
        # Explicit wrapping avoids natural-width/auto-wrap feedback. This retains
        # the original English shadow, disabled opacity and separate highlight.
        put(23,enum('HorizontalAlignment','EHorizontalAlignment','HAlign_Left',byte=True))
        cap=props.find(get(13),'TextSizeCap')
        put(18,boolean('AutoWrapText',False),number('WrapTextAt',struct.unpack('<f',cap.raw)[0]))

    if path.endswith('/StatusMenu/ItemDisplay'):
        # Reading-leading icon, then the flexible name, then the existing count.
        # Culture reverses the row in Arabic without mirroring the icon overlays.
        put(18,objectarray('Slots',[19,20,21]))

    if path.endswith('/Title/TitleScreenUI'):
        # The user explicitly requested replacing this button's label. The
        # old key is shared with export 160 (credits screen heading), so keep
        # the entire localization resource intact and override only this label.
        text='تعريب MIZO و ABDULAZIZ'
        encoded=(text+'\0').encode('utf-16le')
        invariant=struct.pack('<Ibii',2,-1,1,-len(encoded)//2)+encoded
        put(163,props.Prop('Text','TextProperty',idx=0,raw=invariant))
        native(163);justify(get(163),'Center')

    if path.endswith('/StatusMenu/EquipDisplay'):
        # Keep the original icon/empty-icon/indicator canvas as a single unit.
        # Move both occupied and empty text layers to the same fill-width region.
        put(12,objectarray('Slots',[17,14]))
        text_canvas=new('CanvasPanel','RTL_EquipmentText',tree,[objectarray('Slots',[15,16])])
        for n in (15,16):
            put(n,objectprop('Parent',text_canvas))
            offsets=props.find(props.find(get(n),'LayoutData').children,'Offsets').children
            setprop(offsets,number('Left',0));setprop(offsets,number('Right',0))
        icon_bounds=new('SizeBox','RTL_EquipmentIconBounds',tree,[
            number('WidthOverride',94.44444274902344),boolean('bOverride_WidthOverride',True),
            number('HeightOverride',68),boolean('bOverride_HeightOverride',True)])
        icon_slot=new('SizeBoxSlot','RTL_EquipmentIconContent',icon_bounds,[
            objectprop('Parent',icon_bounds),objectprop('Content',13)])
        put(icon_bounds,objectarray('Slots',[icon_slot]));put(13,objectprop('Slot',icon_slot))
        group=row('RTL_EquipmentRow',[(icon_bounds,False),(text_canvas,True)])
        for n in ids(group):
            put(n,margin('Padding',0,0,0,0),
                enum('VerticalAlignment','EVerticalAlignment','VAlign_Fill',byte=True))
        put(ids(group)[0],margin('Padding',0,0,8,0),
            enum('VerticalAlignment','EVerticalAlignment','VAlign_Center',byte=True))
        put(tree,objectprop('RootWidget',group))
        flow(get(13),'LeftToRight')
        # Levels/bars follow the reading-leading edge below the name, without
        # reversing the level meter itself or changing its numeric direction.
        flow(get(31));flow(get(22),'LeftToRight');flow(get(27),'LeftToRight')
        put(35,enum('HorizontalAlignment','EHorizontalAlignment','HAlign_Left',byte=True),
            margin('Padding',0,-4,0,-12))

    if path.endswith('/Journal/JournalMenu'):
        # The footer location is intentionally physical bottom-left. Its inner
        # label/value row still follows culture, but no longer fills 865 units.
        put(68,objectarray('Slots',[72,71]))
        put(37,boolean('bAutoSize',True))
        put(50,boolean('bAutoSize',True))
        layout=props.find(get(50),'LayoutData').children
        setprop(layout,structprop('Anchors','Anchors',[vector('Minimum',0,.5),vector('Maximum',0,.5)]))
        put(61,number('MinDesiredWidth',0))

    # Top-aligned paragraph surfaces only. The first baseline and glyph metrics
    # remain unchanged; the extra advance is visible only between actual lines.
    # Do not modify CommonTextBlock styles, names, buttons or centered cinematics.
    prose={
        '/UI/Widgets/FS_DescriptionText':(10,),
        '/UI/Menus/Journal/JournalMenu':(57,58),
        '/UI/Menus/Journal/Guides_Menu':(50,),
        '/UI/Menus/ReadTextUI':(26,),
        '/UI/DialogueSystem/DialogueScreen':(43,),
    }
    for suffix,indices in prose.items():
        if not path.endswith(suffix):continue
        for n in indices:
            assert ref(pk,pk.exports[n-1][0]) in ('RichTextBlock','CommonRichTextBlock','FB_AnimRichTextBlock')
            old=props.find(get(n),'LineHeightPercentage')
            height=struct.unpack('<f',old.raw)[0] if old else 1.0
            put(n,number('LineHeightPercentage',height*1.05))

    if path.endswith('/HUD/Widgets/ConsumableHUD'):
        assert ref(pk,15)=='Itemname' and ref(pk,17)=='ItemIcon'
        # The original 470-unit text rectangle right-justifies Arabic at its far
        # edge. Measure the text itself, retaining that width only as a wrap cap.
        # Derive the horizontal attachment from the existing icon slot, not HUD
        # screen coordinates; preserve all original vertical and icon geometry.
        icon=props.find(get(10),'LayoutData').children
        label=props.find(get(11),'LayoutData').children
        offsets=props.find(icon,'Offsets').children
        x=struct.unpack('<f',props.find(offsets,'Left').raw)[0]
        width=struct.unpack('<f',props.find(offsets,'Right').raw)[0]
        pivot=struct.unpack('<ff',props.find(icon,'Alignment').raw)[0]
        anchor=struct.unpack('<ff',props.find(props.find(icon,'Anchors').children,'Minimum').raw)[0]
        old=props.find(label,'Offsets').children
        wrap=struct.unpack('<f',props.find(old,'Right').raw)[0]
        setprop(old,number('Left',x+width*(1-pivot)+12))
        setprop(label,structprop('Anchors','Anchors',[vector('Minimum',anchor,0),vector('Maximum',anchor,0)]))
        setprop(label,vector('Alignment',0,0))
        put(11,boolean('bAutoSize',True))
        native(15)
        put(15,number('MinDesiredWidth',0),number('WrapTextAt',wrap))

    if currency_menu:
        coin=next(i+1 for i in range(original_count) if ref(pk,i+1)=='CoinDisplay')
        slot=struct.unpack('<i',props.find(get(coin),'Slot').raw)[0]
        parent=struct.unpack('<i',props.find(get(slot),'Parent').raw)[0]
        outer=struct.unpack('<i',props.find(get(parent),'Slot').raw)[0]
        # Original decorative frame follows its canvas. Give the canvas a natural
        # minimum-sized content box instead of a negatively inset item rectangle.
        box=new('SizeBox','RTL_CurrencyBounds',tree,[
            number('MinDesiredWidth',154),boolean('bOverride_MinDesiredWidth',True),
            number('MinDesiredHeight',40),boolean('bOverride_MinDesiredHeight',True)])
        bs=new('SizeBoxSlot','RTL_CurrencyContent',box,[objectprop('Parent',box),objectprop('Content',coin),
            # The inventory frame ends 18 units before its parent canvas.
            # Include that existing inset so the natural-width group remains
            # inside the frame even at the largest supported integer balance.
            margin('Padding',12,6,30,6),
            enum('HorizontalAlignment','EHorizontalAlignment','HAlign_Center',byte=True),
            enum('VerticalAlignment','EVerticalAlignment','VAlign_Center',byte=True)])
        put(box,objectarray('Slots',[bs]),objectprop('Slot',slot))
        put(coin,objectprop('Slot',bs),vector('IconsPosOverrideTarget',0,0),
            props.Prop('DisplayCountCap','IntProperty',idx=0,raw=struct.pack('<i',2147483647)))
        put(slot,objectprop('Content',box),boolean('bAutoSize',True),
            structprop('LayoutData','AnchorData',[margin('Offsets'),
                structprop('Anchors','Anchors',[vector('Minimum',0,0),vector('Maximum',0,0)])]))
        put(outer,boolean('bAutoSize',True))

    if path.endswith('/HUD/Widgets/GuideGotNotif'):
        # Preserve Box and its slide/fade animation; only replace the internal
        # fixed-height canvas arrangement by a desired-height vertical layout.
        column=new('VerticalBox','RTL_NotificationText',tree,[])
        slots=[]
        for child,pad in [(23,(16,12,16,4)),(24,(16,0,16,12))]:
            s=new('VerticalBoxSlot','RTL_NotificationTextSlot'+str(child),column,[
                objectprop('Parent',column),objectprop('Content',child),childsize(False),
                margin('Padding',*pad),enum('HorizontalAlignment','EHorizontalAlignment','HAlign_Fill',byte=True)])
            put(child,objectprop('Slot',s));slots.append(s)
        put(column,objectarray('Slots',slots),objectprop('Slot',48))
        put(48,objectprop('Content',column));put(14,objectarray('Slots',[]))
        put(24,objectarray('Slots',[26,27]));flow(get(24))
        put(26,childsize(True));put(27,childsize(False),margin('Padding',6,0,0,0))
        put(44,boolean('bOverride_MaxDesiredWidth',False))
        for n in (22,23):
            native(n)
            put(n,number('MinDesiredWidth',0),number('WrapTextAt',256),
                enum('WrappingPolicy','ETextWrappingPolicy','ETextWrappingPolicy::DefaultWrapping'))
        native(21,numeric=True)
        # 400 is the existing HUD allocation. Min height preserves its original
        # compact frame; long titles grow the frame rather than escaping below it.
        bounds=new('SizeBox','RTL_NotificationBounds',tree,[number('WidthOverride',400),
            boolean('bOverride_WidthOverride',True),number('MinDesiredHeight',105),
            boolean('bOverride_MinDesiredHeight',True)])
        bs=new('SizeBoxSlot','RTL_NotificationContent',bounds,[objectprop('Parent',bounds),objectprop('Content',25)])
        put(bounds,objectarray('Slots',[bs]),objectprop('Slot',15));put(25,objectprop('Slot',bs))
        put(15,objectprop('Content',bounds))
        for n in (15,18):
            put(n,boolean('bAutoSize',True),structprop('LayoutData','AnchorData',[
                margin('Offsets'),structprop('Anchors','Anchors',[vector('Minimum',0,0),vector('Maximum',0,0)])]))
    if path.endswith('/HUD/FS_PlayerHUD'):
        assert ref(pk,44)=='GuideGotNotif'
        put(34,boolean('bAutoSize',True))

    if path.endswith('/OptionsMenu/OptionsMenu_OptionSelect'):
        assert ref(pk,23)=='OptionText'
        # Auto-sized canvas text and automatic wrapping form a width feedback
        # loop after culture changes. Allocate the actual gap between arrows.
        put(22,boolean('bAutoSize',True),structprop('LayoutData','AnchorData',[
            margin('Offsets',42,0,42,0),
            structprop('Anchors','Anchors',[vector('Minimum',0,.5),vector('Maximum',1,.5)]),
            vector('Alignment',0,.5)]))

    if path.endswith('/Input/MenuButtonHintWidget'):
        assert ref(pk,7)=='Hinttext'
        # A WrapBox must measure whole action groups before allocating width.
        # Give long labels an explicit ceiling without auto-wrap feedback.
        put(7,boolean('AutoWrapText',False),number('WrapTextAt',270))
        put(13,boolean('bOverride_HeightOverride',False),
            boolean('bOverride_MinDesiredHeight',True),number('MinDesiredHeight',32))

    if path.endswith('/Menus/PauseMenu'):
        # Centered Auto-sized slots must measure complete short labels. Wrapping
        # feeds their previous desired width back into measurement at 720p.
        # Multiline confirmation/warning text keeps its original wrapping.
        for n in (91,95,96,97,98,99,100,101,102,103):
            native(n)
            justify(get(n),'Center')

    if path.endswith('/Menus/OptionsMenu'):
        for i,e in enumerate(pk.exports[:original_count]):
            if ref(pk,i+1)!='ConfirmDialogueText_1':continue
            slot=struct.unpack('<i',props.find(get(i+1),'Slot').raw)[0]
            put(slot,structprop('LayoutData','AnchorData',[margin('Offsets',24,17,24,0),
                structprop('Anchors','Anchors',[vector('Minimum',0,0),vector('Maximum',1,0)]),
                vector('Alignment',0,0)]))

    if path.endswith('/SaveMenu/SaveSlotWidget'):
        assert ref(pk,40)=='PlayTime' and ref(pk,41)=='PlayTimeLabel'
        play = row('RTL_PlayTimeRow',[(41,False),(40,False)])
        for n in ids(play): put(n,margin('Padding',0,0,0,0))
        put(ids(play)[1],margin('Padding',6,0,0,0))
        play_align=row('RTL_PlayTimeAlignment',[(play,True)])
        put(ids(play_align)[0],margin('Padding',0,0,0,0),
            enum('HorizontalAlignment','EHorizontalAlignment','HAlign_Left',byte=True))
        # The upper line must stay beyond the equipment icon strip. The date
        # line below that strip can use the wider original metadata region.
        slot = canvas(13,play_align,'RTL_PlayTimeCanvas',700,77,4,30)
        put(13,objectarray('Slots',[n for n in ids(13) if n not in (20,22)]+[slot]))
        flow(get(46))
        # Keep each label/value pair together at the culture-leading edge.
        # Removing the fill between them frees the original coin area without
        # changing date formatting, the currency widget, or equipment positions.
        put(46,objectarray('Slots',[49,48]))
        put(49,childsize(False),margin('Padding',0,0,0,0))
        put(48,childsize(False),margin('Padding',6,0,0,0))
        date_align=row('RTL_SaveDateAlignment',[(46,True)])
        put(21,objectprop('Content',date_align));put(date_align,objectprop('Slot',21))
        put(ids(date_align)[0],margin('Padding',0,0,0,0),
            enum('HorizontalAlignment','EHorizontalAlignment','HAlign_Left',byte=True))
        for n in (35,38,41,43): native(n,wrap=n==35)
        for n in (36,39,40,42): native(n,numeric=True)

    if path.endswith('/Blueprints/Shop/ShopEntry'):
        assert ref(pk,41)=='ItemDisplay' and ref(pk,50)=='PriceType'
        # Two non-overlapping bands with room for two name lines at original font size.
        # The price switcher retains its sold-out state and stock visibility logic.
        main = row('RTL_ShopPrimary',[(41,True),(50,False)])
        main_slot=canvas(13,main,'RTL_ShopPrimaryCanvas',8,0,8,80)
        put(44,number('HeightOverride',112))
        put(13,objectarray('Slots',[19,main_slot,16]))
        price=row('RTL_PriceAndCoin',[(40,False),(26,False)])
        price_slot=canvas(14,price,'RTL_PriceCanvas',0,0,0,80)
        put(14,objectarray('Slots',[price_slot,20]))
        # Explicit width on the switcher is provided by a reused SizeBox, not
        # by a negative offset or a text-width guess. Existing labels no longer
        # need their old marquee caps: move the wrapper around the switcher.
        put(34,objectprop('Content',25)); put(25,objectprop('Slot',34))
        main_slots=ids(main); price_outer=main_slots[1]
        put(price_outer,objectprop('Content',42))
        put(42,objectprop('Slot',price_outer),number('WidthOverride',160),boolean('bOverride_WidthOverride',True),boolean('bOverride_MaxDesiredWidth',False))
        put(45,objectprop('Content',50));put(50,objectprop('Slot',45))
        # Owned quantity occupies the full second band. Finite stock stays in
        # the price column, above its secondary band (hidden when infinite).
        put(16,structprop('LayoutData','AnchorData',[margin('Offsets',180,80,14,28),
            structprop('Anchors','Anchors',[vector('Minimum',0,0),vector('Maximum',1,0)])]))
        flow(get(32)); put(34,childsize(True));put(35,margin('Padding',8,0,8,0))
        flow(get(33)); put(39,childsize(False));put(36,childsize(True))
        put(20,structprop('LayoutData','AnchorData',[margin('Offsets',0,80,0,28),
            structprop('Anchors','Anchors',[vector('Minimum',0,0),vector('Maximum',1,0)])]))
        put(23,structprop('LayoutData','AnchorData',[margin('Offsets',4,0,4,80),
            structprop('Anchors','Anchors',[vector('Minimum',0,0),vector('Maximum',1,0)])]))
        for n in (25,27,29):native(n,wrap=True)
        put(29,boolean('AutoWrapText',False),number('WrapTextAt',165))
        for n in (24,26,28):native(n,numeric=True)
        # Keep the existing band and data-bound widgets; only remove the fill
        # between the owned label and value. A culture-leading wrapper aligns
        # the whole natural-size group right in Arabic and left in English.
        owned=row('RTL_OwnedAlignment',[(32,True)])
        put(16,objectprop('Content',owned));put(owned,objectprop('Slot',16))
        put(ids(owned)[0],margin('Padding',0,0,0,0),
            enum('HorizontalAlignment','EHorizontalAlignment','HAlign_Left',byte=True))
        put(34,childsize(False),margin('Padding',0,0,0,0))
        put(35,childsize(False),margin('Padding',6,0,0,0))
        native(25)
        for n in (24,25):put(n,number('MinDesiredWidth',0))

    report=[]
    for n, ps in edits.items():
        after={p.name:value(pk,p) for p in ps}
        if after==before[n]:continue
        # Native panel/slot additions use the same preload dependency phases as
        # the game's own widgets. Create referenced objects before deserializing.
        e=pk.exports[n-1]
        refs=[]
        for p in ps:
            if p.type=='ObjectProperty' and p.name!='Parent':refs.append(struct.unpack('<i',p.raw)[0])
            if p.name=='Slots':refs.extend(struct.unpack('<%di'%((len(p.raw)-4)//4),p.raw[4:]))
        old=pk.preload[e[16]:e[16]+sum(e[17:21])]
        a,b,c,d=e[17:21]; deps=old[a:a+b]
        deps=list(dict.fromkeys(deps+[r for r in refs if r and r not in (e[0],e[2],e[3])]))
        e[16]=len(pk.preload);e[18]=len(deps)
        pk.preload.extend(old[:a]+deps+old[a+b:])
        pk.replace_export(n-1,props.Writer(pk).props(ps)+tails[n])
        keys=sorted(k for k in before[n].keys()|after.keys() if before[n].get(k)!=after.get(k))
        report.append(dict(export=n,name=ref(pk,n),cls=ref(pk,e[0]),new=n>original_count,
            reason=['semantic culture-aware row; preserve original data bindings and controls'],
            before={k:before[n].get(k) for k in keys},after={k:after.get(k) for k in keys}))
    return report
