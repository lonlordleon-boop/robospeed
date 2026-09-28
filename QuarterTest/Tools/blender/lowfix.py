# -*- coding: utf-8 -*-
"""下半身の頂点の左右を、x の符号ではなく「どちらの脚の骨に近いか」＋メッシュのつながりで決め直し、
   反対側の脚の重みを外す（片側の重みしか無い頂点は鏡の骨へ付け替える）。
   足をくっ付けて作られたモデルでは靴どうしが x で重なっているので、x の符号では左右を間違えるため。
   実行: blender -b --factory-startup --python lowfix.py -- 入力.glb 出力.glb"""
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
Lp=[wpos(n2i[n]) for n in LN]; Rp=[wpos(n2i[n]) for n in RN]
# つま先の先まで骨の線分を少し伸ばす
def segs(pts):
    s=[(pts[i],pts[i+1]) for i in range(3)]
    d=pts[3]-pts[2]; s.append((pts[3],pts[3]+d*1.5)); return s
def dist_to(pts,p):
    best=1e9
    for a_,b_ in segs(pts):
        ab=b_-a_; t=np.clip(np.dot(p-a_,ab)/max(1e-9,np.dot(ab,ab)),0,1); best=min(best,np.linalg.norm(p-(a_+ab*t)))
    return best
hipy=wpos(n2i['Hips'])[1]
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        P=rd(pr['attributes']['POSITION']); J=rd(pr['attributes']['JOINTS_0']).astype(int); W=rd(pr['attributes']['WEIGHTS_0'])
        idx=rd(pr['indices']).astype(int)[:,0]; nv=len(P)
        lw=np.array([sum(W[v,k] for k in range(4) if J[v,k] in Lset) for v in range(nv)])
        rw=np.array([sum(W[v,k] for k in range(4) if J[v,k] in Rset) for v in range(nv)])
        cand=np.where(((lw+rw)>0.02)&(P[:,1]<hipy))[0]
        side=np.zeros(nv,int)
        for v in cand:
            dl=dist_to(Lp,P[v]); dr=dist_to(Rp,P[v])
            if dl<0.8*dr: side[v]=1
            elif dr<0.8*dl: side[v]=-1
        nb=[[] for _ in range(nv)]
        for t in range(0,len(idx),3):
            a_,b_,c_=idx[t],idx[t+1],idx[t+2]; nb[a_]+=[b_,c_]; nb[b_]+=[a_,c_]; nb[c_]+=[a_,b_]
        amb=[v for v in cand if side[v]==0]
        for it in range(12):
            ch=0
            for v in amb:
                if side[v]!=0: continue
                s=sum(side[u] for u in nb[v])
                if s>0: side[v]=1; ch+=1
                elif s<0: side[v]=-1; ch+=1
            if ch==0: break
        swapped=0; trimmed=0; left0=0
        for v in cand:
            if side[v]==0: left0+=1; continue
            own=Lset if side[v]==1 else Rset; other=Rset if side[v]==1 else Lset
            ow=sum(W[v,k] for k in range(4) if J[v,k] in own); xw=sum(W[v,k] for k in range(4) if J[v,k] in other)
            if xw<=0: continue
            if ow<=0:
                # 全部が反対側 → 鏡の骨へ付け替え
                for k in range(4):
                    if J[v,k] in other: J[v,k]=mirror[J[v,k]]
                swapped+=1
            else:
                for k in range(4):
                    if J[v,k] in other: W[v,k]=0.0
                s=W[v].sum(); W[v]/=s; trimmed+=1
        wr(pr['attributes']['WEIGHTS_0'],W); wr(pr['attributes']['JOINTS_0'],J)
        print("LF 下半身の対象",len(cand),"個: 反対側の重みを外した",trimmed,"個、鏡の骨へ付け替えた",swapped,"個、決められず",left0,"個")
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("LF 書き出し",DST)
