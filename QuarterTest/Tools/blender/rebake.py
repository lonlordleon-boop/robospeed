# -*- coding: utf-8 -*-
"""girl_v2 から作り直す：胴を伸ばす／肩を下げる／脚を左右対称にして平行移動で広げる
   → メッシュを新しい素の姿勢に焼き直す → 腿ウェイトを股関節で切る。
   脚は「回転」ではなく「平行移動」で広げる。回転だと足首の皮が捻れて靴が引き伸ばされる。
   実行: blender -b --factory-startup --python rebake.py -- 入力.glb 出力.glb 胴倍率 肩下げ 脚広げ"""
import json, struct, sys, os
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,DST=a[0],a[1]; SS=float(a[2]); SD=float(a[3]); SPREAD=float(a[4])
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
    return np.array([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),
                     2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]).reshape(3,3)
def wd(i):
    ch=[]; j=i
    while j is not None: ch.append(j); j=parent.get(j)
    M=np.eye(4)
    for j in reversed(ch):
        nd=nodes[j]; L=np.eye(4)
        L[:3,:3]=q2m(np.array(nd.get('rotation',[0,0,0,1]),float))@np.diag(np.array(nd.get('scale',[1,1,1]),float))
        L[:3,3]=np.array(nd.get('translation',[0,0,0]),float); M=M@L
    return M
sk=G['skins'][0]; jt=sk['joints']
IBM0=rd(sk['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1)
delta={}
def move(name,wv):
    i=n2i[name]; Rp=wd(parent[i])[:3,:3]; d=np.linalg.inv(Rp)@np.array(wv,float)
    t=np.array(nodes[i].get('translation',[0,0,0]),float)
    nodes[i]['translation']=(t+d).tolist(); delta[i]=delta.get(i,np.zeros(3))+d
for b in ['Spine02','Spine01','Spine','neck','Head']:
    i=n2i[b]; t=np.array(nodes[i].get('translation',[0,0,0]),float)
    nt=t*SS; delta[i]=nt-t; nodes[i]['translation']=nt.tolist()
for b in ['LeftShoulder','RightShoulder']: move(b,[0,-SD,0])
lx=wd(n2i['LeftUpLeg'])[0,3]; rx=wd(n2i['RightUpLeg'])[0,3]; c=-(lx+rx)/2.0
move('LeftUpLeg',[c+SPREAD,0,0]); move('RightUpLeg',[c-SPREAD,0,0])
M1=[wd(j) for j in jt]; S=[M1[k]@IBM0[k] for k in range(len(jt))]
prim=G['meshes'][0]['primitives'][0]; at=prim['attributes']
P=rd(at['POSITION']); Nn=rd(at['NORMAL']); Jj=rd(at['JOINTS_0']).astype(int); W=rd(at['WEIGHTS_0'])
P2=np.zeros_like(P); N2=np.zeros_like(Nn)
for v in range(len(P)):
    acc=np.zeros((4,4))
    for k in range(4):
        if W[v,k]>0: acc+=W[v,k]*S[Jj[v,k]]
    if abs(acc[3,3])<1e-9: acc=np.eye(4)
    P2[v]=(acc@np.array([P[v,0],P[v,1],P[v,2],1.0]))[:3]
    nv=acc[:3,:3]@Nn[v]; l=np.linalg.norm(nv); N2[v]=nv/l if l>1e-9 else Nn[v]
wr(at['POSITION'],P2); wr(at['NORMAL'],N2)
ac=G['accessors'][at['POSITION']]; ac['min']=P2.min(0).tolist(); ac['max']=P2.max(0).tolist()
wr(sk['inverseBindMatrices'],np.array([np.linalg.inv(M1[k]) for k in range(len(jt))]).transpose(0,2,1).reshape(-1,16))
for an in G['animations']:
    for chn in an['channels']:
        tg=chn['target']
        if tg['path']!='translation' or tg.get('node') not in delta: continue
        smp=an['samplers'][chn['sampler']]; v=rd(smp['output'])
        if v.shape[1]==3: wr(smp['output'],v+delta[tg['node']])
nm={k:i for i,k in enumerate([nodes[j].get('name','') for j in jt])}
LEG=[nm['LeftUpLeg'],nm['RightUpLeg']]; HIP=nm['Hips']
y0,y1=P2[:,1].min(),P2[:,1].max(); H=y1-y0
hj=wd(n2i['LeftUpLeg'])[1,3]; LO=hj-0.010*H; HI=hj+0.050*H
for v in range(len(P2)):
    t=min(1.0,max(0.0,(P2[v,1]-LO)/(HI-LO))); keep=1.0-t*t*(3-2*t)
    if keep>0.999: continue
    moved=0.0
    for k in range(4):
        if Jj[v,k] in LEG and W[v,k]>0:
            b=W[v,k]; W[v,k]=b*keep; moved+=b-W[v,k]
    if moved<=0: continue
    slot=-1; weak=0; ww=2.0
    for k in range(4):
        if Jj[v,k]==HIP: slot=k; break
        if W[v,k]<ww: ww=W[v,k]; weak=k
    if slot<0: slot=weak; Jj[v,slot]=HIP; W[v,slot]=0.0
    W[v,slot]+=moved; s=W[v].sum()
    if s>1e-6: W[v]/=s
# 反対側の脚への重みを掃除する。
# 元のモデルは両足がくっついた状態で自動リグされたため、靴や脚の内側の頂点が
# 反対側の脚の骨にも重み付けされている（下半身の半分以上、最大0.668）。
# そのままだと脚を離すたびに反対側の骨が引き戻し、靴が引き伸ばされる。
# 素の姿勢での左右（X の符号）で側を決め、股関節より下の頂点だけ対象にする。
Lset={i for n,i in nm.items() if n.startswith('Left')}
Rset={i for n,i in nm.items() if n.startswith('Right')}
cleaned=0
#
# 側の判定は「左右どちらの脚の重みが大きいか」で行う。
# 以前は素の姿勢の X の符号で判定していたが、両足をくっ付けて作られたモデルでは
# 靴も内腿も左右が X で重なっており、判定を誤る。さらに sidefix.py が
# メッシュのつながりで側を決めた後だと、その判定と食い違って
# 片側の脚の重みごと消してしまい、隣の頂点との差が跳ね上がって
# 腰まわりにトゲや穴が出ていた。
kneeY=min(wd(n2i["LeftLeg"])[1,3], wd(n2i["RightLeg"])[1,3])
for v in range(len(P2)):
    if P2[v,1] > kneeY: continue                # 膝より上は触らない（股は両脚に半々で結ぶのが正しい）
    lw=sum(W[v,k] for k in range(4) if Jj[v,k] in Lset)
    rw=sum(W[v,k] for k in range(4) if Jj[v,k] in Rset)
    if min(lw,rw) < 0.02: continue              # 片側だけの頂点は掃除の対象外
    wrong = Rset if lw > rw else Lset
    removed=0.0
    for k in range(4):
        if Jj[v,k] in wrong and W[v,k]>0:
            removed+=W[v,k]; W[v,k]=0.0
    if removed<=0: continue
    s=W[v].sum()
    if s>1e-6: W[v]/=s; cleaned+=1
    else: pass                                   # 全部が反対側だった頂点は元に戻せないので触らない
print("CLEAN 反対側の重みを外した頂点", cleaned)
wr(at['WEIGHTS_0'],W); wr(at['JOINTS_0'],Jj)
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))
out+=struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out)
print("REBAKE 胴x%.2f 肩-%.3f 脚広げ%.3f → %s"%(SS,SD,SPREAD,DST))
