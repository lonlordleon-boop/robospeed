# -*- coding: utf-8 -*-
"""headfront / head_end の回転カーブが、クリップの中でどれだけ動いているか（素の姿勢からの最大角）。"""
import json, struct, sys, math
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]
raw=open(SRC,'rb').read(); ln,ty=struct.unpack_from('<II',raw,12); G=json.loads(raw[20:20+ln])
off=12; ck=[]
while off<len(raw):
    l,t=struct.unpack_from('<II',raw,off); off+=8; ck.append((t,off,l)); off+=l
Jm={t:(o,l) for t,o,l in ck}; BO,BL=Jm[0x004E4942]; bd=raw[BO:BO+BL]
COMP={5126:('f',4)}; NUM={'SCALAR':1,'VEC3':3,'VEC4':4}
def rd(i):
    ac=G['accessors'][i]; n=NUM[ac['type']]; bv=G['bufferViews'][ac['bufferView']]; b=bv.get('byteOffset',0)+ac.get('byteOffset',0); st=bv.get('byteStride') or n*4
    return np.array([struct.unpack_from('<'+'f'*n,bd,b+k*st) for k in range(ac['count'])],float)
nodes=G['nodes']
for an in G['animations']:
    for c in an['channels']:
        nm=nodes[c['target']['node']].get('name')
        if nm not in ('headfront','head_end','Head') or c['target']['path']!='rotation': continue
        s=an['samplers'][c['sampler']]; v=rd(s['output'])
        if s.get('interpolation')=='CUBICSPLINE': v=v[1::3]
        r=np.array(nodes[c['target']['node']].get('rotation',[0,0,0,1]),float)
        angs=[2*math.degrees(math.acos(min(1,abs(float(np.dot(r,q)/np.linalg.norm(q)))))) for q in v]
        print("LM %-11s %-9s 素の姿勢からの回転 最大%5.1f° 平均%5.1f°"%(an['name'],nm,max(angs),sum(angs)/len(angs)))
