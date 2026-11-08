import struct
def tables(d):
    n,=struct.unpack_from('>H',d,4); t={}
    for i in range(n):
        tag,cs,off,ln=struct.unpack_from('>4sIII',d,12+16*i); t[tag.decode()]=(off,ln)
    return t
def cmap(d):
    t=tables(d); o=t['cmap'][0]; n,=struct.unpack_from('>H',d,o+2); best=None
    for i in range(n):
        pid,eid,off=struct.unpack_from('>HHI',d,o+4+8*i)
        fmt,=struct.unpack_from('>H',d,o+off)
        if fmt in (4,12) and (best is None or fmt==12): best=(o+off,fmt)
    s,fmt=best; cps={}
    if fmt==4:
        segx2,=struct.unpack_from('>H',d,s+6); seg=segx2//2
        ends=struct.unpack_from('>%dH'%seg,d,s+14); starts=struct.unpack_from('>%dH'%seg,d,s+16+segx2)
        deltas=struct.unpack_from('>%dh'%seg,d,s+16+2*segx2); ro=s+16+3*segx2
        ros=struct.unpack_from('>%dH'%seg,d,ro)
        for i in range(seg):
            for c in range(starts[i],ends[i]+1):
                if c==0xffff: continue
                if ros[i]==0: g=(c+deltas[i])&0xffff
                else:
                    a=ro+2*i+ros[i]+2*(c-starts[i]); g,=struct.unpack_from('>H',d,a)
                    if g: g=(g+deltas[i])&0xffff
                if g: cps[c]=g
    else:
        n,=struct.unpack_from('>I',d,s+12)
        for i in range(n):
            a,b,g=struct.unpack_from('>III',d,s+16+12*i)
            for c in range(a,b+1): cps[c]=g+c-a
    return cps
def name(d):
    t=tables(d); o=t['name'][0]; n,so=struct.unpack_from('>HH',d,o+2); out={}
    for i in range(n):
        pid,eid,lid,nid,ln,off=struct.unpack_from('>6H',d,o+6+12*i)
        if pid==3 and lid==0x409: out[nid]=d[o+so+off:o+so+off+ln].decode('utf-16-be')
    return out
