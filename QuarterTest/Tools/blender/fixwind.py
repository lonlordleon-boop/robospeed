# -*- coding: utf-8 -*-
"""三角形の頂点の並び順（表裏の向き）を、その頂点が持つ法線に合わせてそろえる。
   Unity は裏向きの面を描かないため、並び順が逆の面はそこだけ穴が開き、
   奥にあるもの（肌など）が透けて見えていた。ブラウザ側は両面描画にしていたので気づけなかった。
   法線（陰影の元）は触らず、並び順だけを入れ替えるので、見た目の陰影は変わらない。
   実行: blender -b --factory-startup --python fixwind.py -- 入力.glb 出力.glb"""
import json, struct, sys, os
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,DST=a[0],a[1]
raw=open(SRC,'rb').read(); off=12; ck=[]
while off<len(raw):
    ln,ty=struct.unpack_from('<II',raw,off); off+=8; ck.append((ty,off,ln)); off+=ln
Jm={t:(o,l) for t,o,l in ck}
G=json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO,BL=Jm[0x004E4942]; bd=bytearray(raw[BO:BO+BL])
COMP={5121:('B',1),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}
def lay(i):
    ac=G['accessors'][i]; n=NUM[ac['type']]; f,s=COMP[ac['componentType']]
    bv=G['bufferViews'][ac['bufferView']]
    return ac,n,f,bv.get('byteOffset',0)+ac.get('byteOffset',0), bv.get('byteStride') or n*s
def rd(i):
    ac,n,f,b,st=lay(i); return np.array([struct.unpack_from('<'+f*n,bd,b+k*st) for k in range(ac['count'])],float)
def wr(i,arr):
    ac,n,f,b,st=lay(i)
    for k in range(ac['count']): struct.pack_into('<'+f*n,bd,b+k*st,*arr[k])
total=0; flipped=0
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        if 'NORMAL' not in pr['attributes']:
            print("FW 法線が無いので判定できない"); continue
        P=rd(pr['attributes']['POSITION']); N=rd(pr['attributes']['NORMAL'])
        idx=rd(pr['indices']).astype(np.int64)[:,0]
        tri=idx.reshape(-1,3)
        a0=P[tri[:,0]]; a1=P[tri[:,1]]; a2=P[tri[:,2]]
        fn=np.cross(a1-a0, a2-a0)
        vn=(N[tri[:,0]]+N[tri[:,1]]+N[tri[:,2]])
        d=(fn*vn).sum(1)
        bad=d<0
        total+=len(tri); flipped+=int(bad.sum())
        tri[bad]=tri[bad][:,[0,2,1]]     # 2番目と3番目を入れ替えて向きを反転
        out=tri.reshape(-1,1)
        wr(pr['indices'], out)
print("FW 三角形 %d 個中、向きが逆だった %d 個 (%.2f%%) をそろえた"%(total,flipped,100*flipped/max(1,total)))
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("FW 書き出し",DST,os.path.getsize(DST))
