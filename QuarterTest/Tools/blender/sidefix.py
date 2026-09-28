# -*- coding: utf-8 -*-
"""脚の重みの左右を、元のメッシュのつながりで決め直す（結び直し rebake.py の前に掛ける）。
   自動リグは、くっ付けて作られた両足の靴の頂点に左右の脚の重みを半々に付けている。
   その状態で脚の付け根を動かして結び直すと、靴の頂点が半分しか動かず、靴が中心線へ引き伸ばされた形で
   固定されてしまう（→ 歩くたびに踵がくっ付いて見える）。
   膝より下は左右の靴が面でつながっていないので、つながりで分けた2つの塊を、足首の骨に近いほうで左右に決める。
   それより上（内腿は面でつながっている）は、はっきりした頂点の多数決で決める。
   実行: blender -b --factory-startup --python sidefix.py -- 入力.glb 出力.glb"""
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
LN=['LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase']; RN=['RightUpLeg','RightLeg','RightFoot','RightToeBase']
Lset={jn.index(n) for n in LN}; Rset={jn.index(n) for n in RN}
mirror={jn.index(l):jn.index(r) for l,r in zip(LN,RN)}; mirror.update({jn.index(r):jn.index(l) for l,r in zip(LN,RN)})
kneeY=min(wpos(n2i['LeftLeg'])[1], wpos(n2i['RightLeg'])[1])
ankleL=wpos(n2i['LeftFoot']); ankleR=wpos(n2i['RightFoot'])
print("SF 膝の高さ %.3f  足首 左%s 右%s"%(kneeY,np.round(ankleL,3),np.round(ankleR,3)))
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        P=rd(pr['attributes']['POSITION']); J=rd(pr['attributes']['JOINTS_0']).astype(int); W=rd(pr['attributes']['WEIGHTS_0'])
        idx=rd(pr['indices']).astype(int)[:,0]; nv=len(P)
        lw=np.array([sum(W[v,k] for k in range(4) if J[v,k] in Lset) for v in range(nv)])
        rw=np.array([sum(W[v,k] for k in range(4) if J[v,k] in Rset) for v in range(nv)])
        # --- 膝より下：つながりで塊に分ける ---
        below=P[:,1]<kneeY-0.01
        par=list(range(nv))
        def find(x):
            while par[x]!=x:
                par[x]=par[par[x]]; x=par[x]
            return x
        # glTF は UV の継ぎ目で頂点が分かれているので、同じ位置の頂点を先につなぐ（溶接）
        keyof={}
        for v in range(nv):
            key=tuple(np.round(P[v],5))
            if key in keyof: par[find(v)]=find(keyof[key])
            else: keyof[key]=v
        for t in range(0,len(idx),3):
            a_,b_,c_=idx[t],idx[t+1],idx[t+2]
            if below[a_] and below[b_]: par[find(a_)]=find(b_)
            if below[a_] and below[c_]: par[find(a_)]=find(c_)
        comp=np.array([find(v) if below[v] else -1 for v in range(nv)])
        # 各足首に一番近い頂点の塊を、その側の塊とする
        def comp_of(pt):
            d=np.linalg.norm(P-pt,axis=1); d[~below]=1e9; return comp[int(np.argmin(d))]
        cL=comp_of(ankleL); cR=comp_of(ankleR)
        side=np.zeros(nv,int)
        side[(comp==cL)]=1; side[(comp==cR)]=-1
        nL=int((side==1).sum()); nR=int((side==-1).sum()); other=int((below&(side==0)).sum())
        print("SF 膝より下: 左の塊 %d 頂点、右の塊 %d 頂点、どちらでもない %d（塊が同じ=%s）"%(nL,nR,other,cL==cR))
        # --- 膝より上（脚の重みを持つ頂点）：はっきりした頂点から多数決で広げる ---
        upper=np.where((~below)&((lw+rw)>0.02))[0]
        for v in upper:
            if lw[v]>=3*rw[v] and lw[v]>0.05: side[v]=1
            elif rw[v]>=3*lw[v] and rw[v]>0.05: side[v]=-1
        nb=[[] for _ in range(nv)]
        for t in range(0,len(idx),3):
            a_,b_,c_=idx[t],idx[t+1],idx[t+2]; nb[a_]+=[b_,c_]; nb[b_]+=[a_,c_]; nb[c_]+=[a_,b_]
        # 継ぎ目で分かれた同位置の頂点どうしも隣とみなす
        twins={}
        for v in range(nv): twins.setdefault(tuple(np.round(P[v],5)),[]).append(v)
        for vs in twins.values():
            if len(vs)>1:
                for v in vs: nb[v]+=[u for u in vs if u!=v]
        amb=[v for v in upper if side[v]==0]
        for it in range(20):
            ch=0
            for v in amb:
                if side[v]!=0: continue
                s=sum(side[u] for u in nb[v])
                if s>0: side[v]=1; ch+=1
                elif s<0: side[v]=-1; ch+=1
            if ch==0: break
        # --- 重みを直す ---
        trimmed=0; swapped=0; undecided=0; skipped_upper=0
        for v in range(nv):
            if (lw[v]+rw[v])<=0.001: continue
            # 膝より上（内腿・股・腰）は触らない。
            # そこは左右の脚が面でつながっており、両脚に半々で結ばれているのが正しい。
            # 片側に寄せると、脚を前後に振ったときに股が裂けて、腰から布のトゲが飛び出す。
            # 直したかったのは「くっ付けて作られた靴」だけなので、膝より下に限る。
            if not below[v]: skipped_upper+=1; continue
            if side[v]==0: undecided+=1; continue
            own=Lset if side[v]==1 else Rset; oth=Rset if side[v]==1 else Lset
            ow=sum(W[v,k] for k in range(4) if J[v,k] in own); xw=sum(W[v,k] for k in range(4) if J[v,k] in oth)
            if xw<=0: continue
            if ow<=0:
                for k in range(4):
                    if J[v,k] in oth: J[v,k]=mirror[J[v,k]]
                swapped+=1
            else:
                # 反対側の重みは、同じ役割の自分側の骨へ移す（Foot→Foot など）。枠が無ければ自分側で一番大きい骨へ
                for k in range(4):
                    if J[v,k] in oth and W[v,k]>0:
                        tgt=mirror[J[v,k]]; slot=next((m for m in range(4) if J[v,m]==tgt),None)
                        if slot is None:
                            slot=next((m for m in range(4) if W[v,m]==0 and m!=k),None)
                            if slot is not None: J[v,slot]=tgt; W[v,slot]=0.0
                        if slot is None: slot=int(np.argmax([W[v,m] if J[v,m] in own else -1 for m in range(4)]))
                        W[v,slot]+=W[v,k]; W[v,k]=0.0
                W[v]/=W[v].sum(); trimmed+=1
        wr(pr['attributes']['WEIGHTS_0'],W); wr(pr['attributes']['JOINTS_0'],J)
        print("SF 反対側の重みを移した %d 個、鏡の骨へ付け替えた %d 個、決められず %d 個、膝より上なので触らず %d 個"%(trimmed,swapped,undecided,skipped_upper))
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("SF 書き出し",DST)
