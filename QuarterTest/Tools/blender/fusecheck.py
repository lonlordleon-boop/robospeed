# -*- coding: utf-8 -*-
"""左右の靴がメッシュとして融合しているか調べる：左足側と右足側の頂点を両方含む三角形（橋渡し面）を数え、位置を出す。
   側は元の重みの多数（脚4本の合計）で決める。"""
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
P=rd(pr['attributes']['POSITION']); J=rd(pr['attributes']['JOINTS_0']).astype(int); W=rd(pr['attributes']['WEIGHTS_0']); idx=rd(pr['indices']).astype(int)[:,0]
lw=np.array([sum(W[v,k] for k in range(4) if J[v,k] in Lset) for v in range(len(P))])
rw=np.array([sum(W[v,k] for k in range(4) if J[v,k] in Rset) for v in range(len(P))])
side=np.where((lw+rw)<0.3,0,np.where(lw>rw,1,-1))
tri=idx.reshape(-1,3)
s=side[tri]
mixed=np.where((s.min(1)==-1)&(s.max(1)==1))[0]
print("FC 三角形",len(tri),"  左右の脚をまたぐ三角形",len(mixed))
if len(mixed):
    c=P[tri[mixed]].mean(1)
    print("FC またぐ三角形の高さ分布(y):", np.histogram(c[:,1],bins=[-0.1,0.02,0.05,0.1,0.15,0.2,0.3,0.4,0.6])[0].tolist())
    print("FC   x範囲 %.3f..%.3f  y範囲 %.3f..%.3f  z範囲 %.3f..%.3f"%(c[:,0].min(),c[:,0].max(),c[:,1].min(),c[:,1].max(),c[:,2].min(),c[:,2].max()))
# 靴の内側の頂点で、左右の重みが半々のものの位置
amb=np.where((lw>0.2)&(rw>0.2)&(P[:,1]<0.12))[0]
print("FC 靴の高さで左右半々の頂点",len(amb),"個  x範囲 %s"%( "%.3f..%.3f"%(P[amb,0].min(),P[amb,0].max()) if len(amb) else "-"))
