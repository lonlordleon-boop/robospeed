# -*- coding: utf-8 -*-
"""頭より上（髪）にある頂点が、頭以外の骨にどれだけ重みを持っているかを調べる。"""
import json, struct, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]
raw=open(SRC,'rb').read(); off=12; ck=[]
while off<len(raw):
    ln,ty=struct.unpack_from('<II',raw,off); off+=8; ck.append((ty,off,ln)); off+=ln
Jm={t:(o,l) for t,o,l in ck}
G=json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO,BL=Jm[0x004E4942]; bd=raw[BO:BO+BL]
COMP={5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def rd(i):
    ac=G['accessors'][i]; n=NUM[ac['type']]; f,s=COMP[ac['componentType']]
    bv=G['bufferViews'][ac['bufferView']]; b=bv.get('byteOffset',0)+ac.get('byteOffset',0); st=bv.get('byteStride') or n*s
    return np.array([struct.unpack_from('<'+f*n,bd,b+k*st) for k in range(ac['count'])],float)
nodes=G['nodes']; skin=G['skins'][0]; joints=skin['joints']; jn=[nodes[j].get('name') for j in joints]
n2i={nd.get('name',''):i for i,nd in enumerate(nodes)}
# 骨のワールド位置（素の姿勢）
parent={}
for i,nd in enumerate(nodes):
    for c in nd.get('children',[]): parent[c]=i
def q2m(q):
    x,y,z,w=q
    return np.array([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]).reshape(3,3)
def wpos(i):
    ch=[];j=i
    while j is not None: ch.append(j); j=parent.get(j)
    M=np.eye(4)
    for j in reversed(ch):
        nd=nodes[j]; L=np.eye(4); L[:3,:3]=q2m(np.array(nd.get('rotation',[0,0,0,1]),float))@np.diag(np.array(nd.get('scale',[1,1,1]),float)); L[:3,3]=np.array(nd.get('translation',[0,0,0]),float); M=M@L
    return M[:3,3]
JP={n:wpos(n2i[n]) for n in jn}
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        P=rd(pr['attributes']['POSITION']); J=rd(pr['attributes']['JOINTS_0']).astype(int); W=rd(pr['attributes']['WEIGHTS_0'])
        # メッシュはスキン適用前の頂点。頭骨の高さより上の頂点＝髪
        headz=JP['Head'][1]; top=P[:,1].max()
        print("HW 頂点数",len(P),"頭骨y %.3f 頂上y %.3f 首y %.3f"%(headz,top,JP['neck'][1]))
        sel=P[:,1]>headz+(top-headz)*0.15
        tot={}
        for vi in np.where(sel)[0]:
            for k in range(4):
                if W[vi,k]>0.001:
                    n=jn[J[vi,k]]; tot.setdefault(n,[0,0.0,0.0]); tot[n][0]+=1; tot[n][1]+=W[vi,k]; tot[n][2]=max(tot[n][2],W[vi,k])
        print("HW 髪の頂点",sel.sum(),"個の重み先:")
        for n,(c,s,mx) in sorted(tot.items(),key=lambda x:-x[1][1]): print("HW   %-14s 頂点%5d 重み合計%8.2f 最大%.3f"%(n,c,s,mx))
