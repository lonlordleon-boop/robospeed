# -*- coding: utf-8 -*-
"""wrongside.py が出した頂点（素の位置で照合）の脚の骨を、左右の鏡の骨へ付け替える。
   実行: blender -b --factory-startup --python sidepatch.py -- 入力.glb 出力.glb 一覧.json"""
import json, struct, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,DST,LST=a[0],a[1],a[2]
raw=open(SRC,'rb').read(); off=12; ck=[]
while off<len(raw):
    ln,ty=struct.unpack_from('<II',raw,off); off+=8; ck.append((ty,off,ln)); off+=ln
Jm={t:(o,l) for t,o,l in ck}
G=json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO,BL=Jm[0x004E4942]; bd=bytearray(raw[BO:BO+BL])
COMP={5121:('B',1),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM={'SCALAR':1,'VEC3':3,'VEC4':4}
def lay(i):
    ac=G['accessors'][i]; n=NUM[ac['type']]; f,s=COMP[ac['componentType']]
    bv=G['bufferViews'][ac['bufferView']]
    return ac,n,f,bv.get('byteOffset',0)+ac.get('byteOffset',0), bv.get('byteStride') or n*s
def rd(i):
    ac,n,f,b,st=lay(i); return np.array([struct.unpack_from('<'+f*n,bd,b+k*st) for k in range(ac['count'])],float)
def wr(i,arr):
    ac,n,f,b,st=lay(i)
    for k in range(ac['count']): struct.pack_into('<'+f*n,bd,b+k*st,*arr[k])
nodes=G['nodes']; jn=[nodes[j].get('name') for j in G['skins'][0]['joints']]
LN=['LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase']; RN=['RightUpLeg','RightLeg','RightFoot','RightToeBase']
mirror={jn.index(l):jn.index(r) for l,r in zip(LN,RN)}; mirror.update({jn.index(r):jn.index(l) for l,r in zip(LN,RN)})
# Blender は Y-up→Z-up に変換しているので、glTF の (x,y,z) は Blender の (x,-z,y)
wrong=np.array(json.load(open(LST))['wrong'])
if len(wrong)==0: print("SP 対象なし"); sys.exit(0)
wrong_g=np.stack([wrong[:,0], wrong[:,2], -wrong[:,1]],1)
n=0
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        P=rd(pr['attributes']['POSITION']); J=rd(pr['attributes']['JOINTS_0']).astype(int)
        for w in wrong_g:
            d=np.linalg.norm(P-w,axis=1); hits=np.where(d<1e-4)[0]
            for v in hits:
                for k in range(4):
                    if J[v,k] in mirror: J[v,k]=mirror[J[v,k]]
                n+=1
        wr(pr['attributes']['JOINTS_0'],J)
print("SP 付け替えた頂点",n,"個（一覧",len(wrong),"件）")
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("SP 書き出し",DST)
