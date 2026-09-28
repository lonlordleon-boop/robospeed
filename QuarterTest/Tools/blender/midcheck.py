# -*- coding: utf-8 -*-
"""腰より下で、体の中心線ぎりぎり（|x|≤しきい値）にあって左右両方の脚の重みを持つ頂点を数える。"""
import json, struct, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]
raw=open(SRC,'rb').read(); off=12; ck=[]
while off<len(raw):
    ln,ty=struct.unpack_from('<II',raw,off); off+=8; ck.append((ty,off,ln)); off+=ln
Jm={t:(o,l) for t,o,l in ck}
G=json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO,BL=Jm[0x004E4942]; bd=raw[BO:BO+BL]
COMP={5121:('B',1),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM={'SCALAR':1,'VEC3':3,'VEC4':4}
def rd(i):
    ac=G['accessors'][i]; n=NUM[ac['type']]; f,s=COMP[ac['componentType']]
    bv=G['bufferViews'][ac['bufferView']]; b=bv.get('byteOffset',0)+ac.get('byteOffset',0); st=bv.get('byteStride') or n*s
    return np.array([struct.unpack_from('<'+f*n,bd,b+k*st) for k in range(ac['count'])],float)
nodes=G['nodes']; jn=[nodes[j].get('name') for j in G['skins'][0]['joints']]
Lset={i for i,n in enumerate(jn) if n in ('LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase')}
Rset={i for i,n in enumerate(jn) if n in ('RightUpLeg','RightLeg','RightFoot','RightToeBase')}
pr=G['meshes'][0]['primitives'][0]
P=rd(pr['attributes']['POSITION']); J=rd(pr['attributes']['JOINTS_0']).astype(int); W=rd(pr['attributes']['WEIGHTS_0'])
lw=np.array([sum(W[v,k] for k in range(4) if J[v,k] in Lset) for v in range(len(P))])
rw=np.array([sum(W[v,k] for k in range(4) if J[v,k] in Rset) for v in range(len(P))])
low=P[:,1]<0.45
both=(lw>0.02)&(rw>0.02)&low
print("MC 腰より下の頂点",low.sum(),"  左右両方の脚の重みを持つ",both.sum())
for th in (0.005,0.01,0.02,0.03):
    m=both&(np.abs(P[:,0])<=th); print("MC   |x|<=%.3f: %d 個  (そのうち反対側の重みが0.3超 %d)"%(th,m.sum(),(m&(np.minimum(lw,rw)>0.3)).sum()))
m=both&(np.abs(P[:,0])<=0.01)
print("MC 例:", [(round(P[v,0],3),round(P[v,1],3),round(lw[v],2),round(rw[v],2)) for v in np.where(m)[0][:8]])
