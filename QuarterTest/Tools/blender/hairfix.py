# -*- coding: utf-8 -*-
"""髪・頭の頂点（頭の重みがすでに6割以上のもの）に混ざっている肩・背骨・腰などの重みを頭（Head）へ寄せる。
   自動リグが、首の後ろに垂れる髪を「肩や背中の一部」と判断して重みを混ぜており、
   頭が動くと髪の殻だけが遅れて地肌が透けるため。
   対象: 首の関節より上にあり、頭（Head+headfront）の重みが 0.05 以上の頂点。
   実行: blender -b --factory-startup --python hairfix.py -- 入力.glb 出力.glb"""
import json, struct, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,DST=a[0],a[1]
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
skin=G['skins'][0]; joints=skin['joints']; jn=[nodes[j].get('name') for j in joints]
HEAD=jn.index('Head'); HF=jn.index('headfront')
necky=wpos(n2i['neck'])[1]     # glTF は Y が上
tot=0; moved={}
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        P=rd(pr['attributes']['POSITION']); J=rd(pr['attributes']['JOINTS_0']).astype(int); W=rd(pr['attributes']['WEIGHTS_0'])
        for vi in range(len(P)):
            if P[vi,1] < necky-0.01: continue   # 境界の取りこぼしを防ぐため 1cm 下まで
            hw=sum(W[vi,k] for k in range(4) if J[vi,k] in (HEAD,HF))
            if hw<=0.2 or hw>=0.995: continue
            # 頭寄りの度合いをなだらかに上げる（0.2 では変えず、0.7 以上で頭だけにする）。
            # しきい値で切ると、境目で「頭だけの頂点」と「半々の頂点」が隣り合い、そこが裂ける。
            # 肩や袖の頂点は頭の重みが 0.05 程度なので、この式では動かない。
            t=(hw-0.2)/0.5; t=max(0.0,min(1.0,t)); ramp=t*t*(3-2*t)
            target=hw+(1.0-hw)*ramp
            if target<=hw+1e-6: continue
            sc_head=target/hw; sc_other=(1.0-target)/(1.0-hw)
            for k in range(4):
                if J[vi,k] in (HEAD,HF): W[vi,k]*=sc_head
                elif W[vi,k]>0:
                    moved[jn[J[vi,k]]]=moved.get(jn[J[vi,k]],0)+1; W[vi,k]*=sc_other
            W[vi]/=W[vi].sum(); tot+=1
        wr(pr['attributes']['WEIGHTS_0'],W); wr(pr['attributes']['JOINTS_0'],J)
print("HF 頭寄りに直した頂点",tot,"個  弱めた重みの元:",sorted(moved.items(),key=lambda x:-x[1]))

# 第二段：首の関節より下にあるのに頭の重みが乗っている頂点から、頭の重みを外す。
# 裾や腿にまで僅かな頭の重みが付いており、首を振るたびにそこが引っ張られて服が伸びるため。
# （この高さに髪は無いことを確かめてある）
strip=0
for mesh in G["meshes"]:
    for pr in mesh["primitives"]:
        P=rd(pr["attributes"]["POSITION"]); J=rd(pr["attributes"]["JOINTS_0"]).astype(int); W=rd(pr["attributes"]["WEIGHTS_0"])
        for vi in range(len(P)):
            if P[vi,1] >= necky: continue
            hw=sum(W[vi,k] for k in range(4) if J[vi,k] in (HEAD,HF))
            if hw<=0.0 or hw>0.6: continue
            for k in range(4):
                if J[vi,k] in (HEAD,HF): W[vi,k]=0.0
            s=W[vi].sum()
            if s<=0: continue
            W[vi]/=s; strip+=1
        wr(pr["attributes"]["WEIGHTS_0"],W)
print("HF 首より下から頭の重みを外した頂点",strip,"個")
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("HF 書き出し",DST)
