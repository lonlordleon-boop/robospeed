# -*- coding: utf-8 -*-
"""GLB の中のアニメ名を付け替える。古い方を捨て、新しい方をその名前にする。
   実行: blender -b --factory-startup --python swap_clip.py -- 入力.glb 出力.glb 新しい名 使いたい名"""
import json, struct, sys
a=sys.argv[sys.argv.index("--")+1:]
SRC,DST,NEW,USE=a[0],a[1],a[2],a[3]
raw=open(SRC,'rb').read(); off=12; ck=[]
while off<len(raw):
    ln,ty=struct.unpack_from('<II',raw,off); off+=8; ck.append((ty,off,ln)); off+=ln
Jm={t:(o,l) for t,o,l in ck}
G=json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO,BL=Jm[0x004E4942]; bd=raw[BO:BO+BL]
anims=[x for x in G['animations'] if x.get('name')!=USE]   # 古い方を捨てる
for x in anims:
    if x.get('name')==NEW: x['name']=USE                    # 新しい方をその名前に
G['animations']=anims
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bd+b'\x00'*((4-len(bd)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))
out+=struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out)
print("CLIPS", [x.get('name') for x in G['animations']], "→", DST)
