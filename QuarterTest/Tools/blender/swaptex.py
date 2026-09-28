# -*- coding: utf-8 -*-
"""GLB に埋め込まれている画像を、別の PNG に差し替える（ブラウザ側にも同じ絵を出すため）。
   古い画像は捨て、バッファを詰め直すのでファイルは太らない。
   実行: blender -b --factory-startup --python swaptex.py -- 入力.glb 差し替えるPNG 出力.glb"""
import json, struct, sys, os
a=sys.argv[sys.argv.index("--")+1:]; SRC,PNG,DST=a[0],a[1],a[2]
raw=open(SRC,'rb').read(); off=12; ck=[]
while off<len(raw):
    ln,ty=struct.unpack_from('<II',raw,off); off+=8; ck.append((ty,off,ln)); off+=ln
Jm={t:(o,l) for t,o,l in ck}
G=json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO,BL=Jm[0x004E4942]; old=raw[BO:BO+BL]
img=G['images'][0]; oldbv=img['bufferView']
new=open(PNG,'rb').read()
print("SW 元の画像 %d バイト → 新しい画像 %d バイト"%(G['bufferViews'][oldbv]['byteLength'],len(new)))
buf=bytearray()
for i,bv in enumerate(G['bufferViews']):
    if i==oldbv:
        data=new
    else:
        o=bv.get('byteOffset',0); data=old[o:o+bv['byteLength']]
    while len(buf)%4: buf.append(0)
    bv['byteOffset']=len(buf); bv['byteLength']=len(data); buf+=data
G['buffers'][0]['byteLength']=len(buf)
img['mimeType']='image/png'
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(buf); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("SW 書き出し",DST,os.path.getsize(DST))
