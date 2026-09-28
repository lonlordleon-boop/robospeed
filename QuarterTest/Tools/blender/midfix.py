# -*- coding: utf-8 -*-
"""股の真ん中（|x| が小さい）にあって左右両方の脚の重みを持つ頂点を、メッシュのつながりで左右に振り分ける。
   足をくっ付けて作られたモデルでは、内腿・靴の内側の頂点が中心線上にあり、自動リグが両脚に半々で重みを付ける。
   そのままだと脚を開いたとき、その頂点が両脚の中間に取り残されて「膜」のように繋がって見える。
   周りの頂点（はっきり左右が決まっているもの）の多数決で側を決め、反対側の重みを外す。
   実行: blender -b --factory-startup --python midfix.py -- 入力.glb 出力.glb"""
import json, struct, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,DST=a[0],a[1]
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
Lset={i for i,n in enumerate(jn) if n in ('LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase')}
Rset={i for i,n in enumerate(jn) if n in ('RightUpLeg','RightLeg','RightFoot','RightToeBase')}
n2i={nd.get('name',''):i for i,nd in enumerate(nodes)}
total=0
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        P=rd(pr['attributes']['POSITION']); J=rd(pr['attributes']['JOINTS_0']).astype(int); W=rd(pr['attributes']['WEIGHTS_0'])
        idx=rd(pr['indices']).astype(int)[:,0]
        nv=len(P)
        lw=np.array([sum(W[v,k] for k in range(4) if J[v,k] in Lset) for v in range(nv)])
        rw=np.array([sum(W[v,k] for k in range(4) if J[v,k] in Rset) for v in range(nv)])
        # 側の初期値：はっきりしている頂点だけ（片側の重みがもう片側の3倍以上）
        side=np.zeros(nv,int)
        side[(lw>0.05)&(lw>=3*rw)]=1; side[(rw>0.05)&(rw>=3*lw)]=-1
        amb=np.where((lw>0.02)&(rw>0.02)&(side==0))[0]
        # 隣接表
        nb=[[] for _ in range(nv)]
        for t in range(0,len(idx),3):
            a_,b_,c_=idx[t],idx[t+1],idx[t+2]
            nb[a_]+= [b_,c_]; nb[b_]+=[a_,c_]; nb[c_]+=[a_,b_]
        # 多数決を繰り返して広げる
        for it in range(8):
            changed=0
            for v in amb:
                if side[v]!=0: continue
                s=sum(side[u] for u in nb[v])
                if s>0: side[v]=1; changed+=1
                elif s<0: side[v]=-1; changed+=1
            if changed==0: break
        fixed=0
        for v in amb:
            if side[v]==0: continue
            drop=Rset if side[v]==1 else Lset
            ex=0.0
            for k in range(4):
                if J[v,k] in drop: ex+=W[v,k]; W[v,k]=0.0
            if ex<=0: continue
            keep=[k for k in range(4) if W[v,k]>0]
            s=W[v].sum()
            if s>0: W[v]/=s
            fixed+=1
        wr(pr['attributes']['WEIGHTS_0'],W); wr(pr['attributes']['JOINTS_0'],J); total+=fixed
        print("MF あいまいな頂点",len(amb),"個 → 振り分けた",fixed,"個（決められず残した",int((side[amb]==0).sum()),"個）")
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("MF 書き出し",DST)
