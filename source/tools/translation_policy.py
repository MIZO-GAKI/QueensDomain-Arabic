"""Narrow exception for the user-authorized main-menu button label only."""
import struct
import props
from ui_audit import ref

def check_credit_widget(pk):
    assert ref(pk,163)=='UseButtontext'
    ps,_=props.Reader(pk,pk.export_data(162)).props(0)
    encoded=('تعريب MIZO و ABDULAZIZ'+'\0').encode('utf-16le')
    assert props.find(ps,'Text').raw==struct.pack('<Ibii',2,-1,1,-len(encoded)//2)+encoded
