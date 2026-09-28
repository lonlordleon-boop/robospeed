# -*- coding: utf-8 -*-
"""足首の関節より下（靴）の頂点に混ざっている すね（Leg）・腿（UpLeg）の重みを、その側の足（Foot）へ寄せる。
   自動リグが靴の内側の底の頂点にまで すね の影響を残しており、膝が曲がると底の頂点が すね に引かれて
   靴が伸びる／反対の靴へ食い込むため。
   実行: blender -b --factory-startup --python footfix.py -- 入力.glb 出力.glb [足首からの余裕(既定0.01)]"""
import json, struct, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,DST=a[0],a[1]; MARGIN=float(a[2]) if len(a)>2 else 0.01
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
nodes=G['nodes']; parent={}
for i,nd in enumerate(nodes):
    for c in nd.get('children',[]): parent[c]=i
n2i={nd.get('name',''):i for i,nd in enumerate(nodes)}
def q2m(q):
    x,y,z,w=q
    return np.array([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]).reshape(3,3)
def wpos(i):
    ch=[];j=i
    while j is not None: ch.append(j); j=parent.get(j)
    Mx=np.eye(4)
    for j in reversed(ch):
        nd=nodes[j]; L=np.eye(4); L[:3,:3]=q2m(np.array(nd.get('rotation',[0,0,0,1]),float))@np.diag(np.array(nd.get('scale',[1,1,1]),float)); L[:3,3]=np.array(nd.get('translation',[0,0,0]),float); Mx=Mx@L
    return Mx[:3,3]
jn=[nodes[j].get('name') for j in G['skins'][0]['joints']]
J_=lambda n: jn.index(n)
ankle={ 'L': wpos(n2i['LeftFoot'])[1], 'R': wpos(n2i['RightFoot'])[1] }
print("FF 足首の高さ 左%.3f 右%.3f"%(ankle['L'],ankle['R']))
sides={'L':('LeftFoot','LeftToeBase','LeftLeg','LeftUpLeg'),'R':('RightFoot','RightToeBase','RightLeg','RightUpLeg')}
tot=0; hist={}
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        P=rd(pr['attributes']['POSITION']); J=rd(pr['attributes']['JOINTS_0']).astype(int); W=rd(pr['attributes']['WEIGHTS_0'])
        for v in range(len(P)):
            for s,(F,T,L,U) in sides.items():
                fw=sum(W[v,k] for k in range(4) if J[v,k] in (J_(F),J_(T)))
                if fw<0.05 or P[v,1]>ankle[s]+MARGIN: continue
                ex=0.0
                for k in range(4):
                    if J[v,k] in (J_(L),J_(U)) and W[v,k]>0:
                        hist[jn[J[v,k]]]=hist.get(jn[J[v,k]],0)+1; ex+=W[v,k]; W[v,k]=0.0
                if ex<=0: continue
                slot=next((k for k in range(4) if J[v,k]==J_(F)),None)
                if slot is None: slot=next(k for k in range(4) if W[v,k]==0); J[v,slot]=J_(F)
                W[v,slot]+=ex; W[v]/=W[v].sum(); tot+=1
        wr(pr['attributes']['WEIGHTS_0'],W); wr(pr['attributes']['JOINTS_0'],J)
print("FF 足へ寄せた頂点",tot,"個  外した重みの元:",sorted(hist.items(),key=lambda x:-x[1]))
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("FF 書き出し",DST)
