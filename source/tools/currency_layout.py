"""Dedicated presentation copy for currency; inventory ItemDisplay is unchanged."""
import copy
import struct
from uasset import Package
import props
from ui_audit import ref,value
from ui_layout import setprop,boolean,number,margin,objectarray,vector,enum

SOURCE='QueensDomain/Content/UI/Menus/StatusMenu/ItemDisplay'
TARGET=SOURCE.replace('ItemDisplay','CurrencyDisplay')

def apply(files,report):
    pk=Package(files[SOURCE+'.uasset'],files[SOURCE+'.uexp'])
    changes=copy.deepcopy(report[SOURCE])
    names={'/Game/UI/Menus/StatusMenu/ItemDisplay':'/Game/UI/Menus/StatusMenu/CurrencyDisplay',
           'ItemDisplay_C':'CurrencyDisplay_C','Default__ItemDisplay_C':'Default__CurrencyDisplay_C'}
    pk.names=[names.get(n,n) for n in pk.names]
    patches={
        18:[objectarray('Slots',[19,21])], # hide-name setting remains bound, without an empty fill column
        19:[margin('Padding',6,0,6,0)],
        21:[margin('Padding',0,0,0,0)],
        24:[boolean('bOverride_WidthOverride',False)], # measure every visible digit
        15:[boolean('AutoWrapText',False),number('WrapTextAt',0),number('MinDesiredWidth',0)],
    }
    for n,values in patches.items():
        data=pk.export_data(n-1);ps,end=props.Reader(pk,data).props(0)
        before={p.name:value(pk,p) for p in ps}
        for p in values:setprop(ps,p)
        after={p.name:value(pk,p) for p in ps}
        keys=[k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)]
        pk.replace_export(n-1,props.Writer(pk).props(ps)+data[end:])
        changes.append(dict(export=n,name=ref(pk,n),cls=ref(pk,pk.exports[n-1][0]),
            reason=['currency-only natural-size amount/icon group; preserve data binding'],
            before={k:before.get(k) for k in keys},after={k:after.get(k) for k in keys}))
    files[TARGET+'.uasset'],files[TARGET+'.uexp']=pk.build()
    report[TARGET]=changes
