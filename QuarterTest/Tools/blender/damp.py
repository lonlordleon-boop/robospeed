# -*- coding: utf-8 -*-
"""指定クリップの指定骨について、素の姿勢からの回転のズレを k 倍に弱める（k=1 で無変更、0 で素の姿勢に固定）。
   新しい回転を足すのではなく、元々ある振りを小さくするだけ。移動カーブは触らない。
   実行: blender -b --factory-startup --python damp.py -- 入力.glb 出力.glb クリップ名 k 骨1,骨2,..."""
import json, struct, sys, math, os
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,DST,CLIP,K=a[0],a[1],a[2],float(a[3]); BONES=set(a[4].split(','))
raw=open(SRC,'rb').read(); off=12; ck=[]
while off<len(raw):
    ln,ty=struct.unpack_from('<II',raw,off); off+=8; ck.append((ty,off,ln)); off+=ln
Jm={t:(o,l) for t,o,l in ck}
G=json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO,BL=Jm[0x004E4942]; bd=bytearray(raw[BO:BO+BL])
COMP={5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def lay(i):
    ac=G['accessors'][i]; n=NUM[ac['type']]; f,s=COMP[ac['componentType']]
    bv=G['bufferViews'][ac['bufferView']]
    return ac,n,f,bv.get('byteOffset',0)+ac.get('byteOffset',0), bv.get('byteStride') or n*s
def rd(i):
    ac,n,f,b,st=lay(i); o=np.zeros((ac['count'],n))
    for k in range(ac['count']): o[k]=struct.unpack_from('<'+f*n,bd,b+k*st)
    return o
def wr(i,arr):
    ac,n,f,b,st=lay(i)
    for k in range(ac['count']): struct.pack_into('<'+f*n,bd,b+k*st,*arr[k])
def slerp(p,q,u):
    d=float(np.dot(p,q))
    if d<0: q=-q; d=-d
    if d>0.9995: r=p+u*(q-p); return r/np.linalg.norm(r)
    th=math.acos(d); s=math.sin(th); return (math.sin((1-u)*th)/s)*p+(math.sin(u*th)/s)*q
nodes=G['nodes']; n2i={nd.get('name',''):i for i,nd in enumerate(nodes)}
an=next(x for x in G['animations'] if x.get('name')==CLIP)
done=[]
for c in an['channels']:
    if c['target']['path']!='rotation': continue
    name=nodes[c['target']['node']].get('name','')
    if name not in BONES: continue
    s=an['samplers'][c['sampler']]; v=rd(s['output'])
    rest=np.array(nodes[c['target']['node']].get('rotation',[0,0,0,1]),float)
    step=3 if s.get('interpolation')=='CUBICSPLINE' else 1
    out=v.copy()
    for k in range(1 if step==3 else 0, len(v), step):
        out[k]=slerp(rest, v[k], K)
    wr(s['output'],out); done.append(name)
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("DAMP",CLIP,"k=%.2f"%K,done,"→",DST)
