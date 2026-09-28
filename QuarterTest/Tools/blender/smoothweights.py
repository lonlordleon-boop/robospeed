# -*- coding: utf-8 -*-
"""重みを、メッシュのつながりに沿って軽くならす。
   一番近い頂点から重みを写すと、隣り合う頂点が別々の骨に付いて段差ができ、そこが伸びる。
   骨4本の枠は守り、合計は1のまま。
   実行: blender -b --factory-startup --python smoothweights.py -- 入力.glb 出力.glb 回数 強さ"""
import json, struct, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,DST=a[0],a[1]; IT=int(a[2]) if len(a)>2 else 2; AL=float(a[3]) if len(a)>3 else 0.5
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
NB=len(G['skins'][0]['joints'])
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        P=rd(pr['attributes']['POSITION']); J=rd(pr['attributes']['JOINTS_0']).astype(int); W=rd(pr['attributes']['WEIGHTS_0'])
        idx=rd(pr['indices']).astype(int)[:,0]; nv=len(P)
        # 同じ位置の頂点をつなぐ（継ぎ目対策）
        key={}; rep=np.arange(nv)
        for v in range(nv):
            k=tuple(np.round(P[v],5))
            if k in key: rep[v]=key[k]
            else: key[k]=v
        nb=[[] for _ in range(nv)]
        for t in range(0,len(idx),3):
            a_,b_,c_=rep[idx[t]],rep[idx[t+1]],rep[idx[t+2]]
            nb[a_]+=[b_,c_]; nb[b_]+=[a_,c_]; nb[c_]+=[a_,b_]
        F=np.zeros((nv,NB))
        for v in range(nv):
            for k in range(4):
                if W[v,k]>0: F[rep[v],J[v,k]]+=W[v,k]
        for _ in range(IT):
            F2=F.copy()
            for v in range(nv):
                if rep[v]!=v or not nb[v]: continue
                F2[v]=(1-AL)*F[v]+AL*F[nb[v]].mean(0)
            s=F2.sum(1,keepdims=True); s[s<1e-9]=1; F=F2/s
        cnt=0
        for v in range(nv):
            f=F[rep[v]]
            top=np.argsort(-f)[:4]; w=f[top]
            if w.sum()<1e-9: continue
            w=w/w.sum()
            if np.abs(np.sort(W[v])[::-1]-np.sort(w)[::-1]).sum()>0.01: cnt+=1
            J[v]=top; W[v]=w
        wr(pr['attributes']['WEIGHTS_0'],W); wr(pr['attributes']['JOINTS_0'],J)
        print("SW %d回ならした（強さ%.2f）。変わった頂点 %d / %d"%(IT,AL,cnt,nv))
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("SW 書き出し",DST)
