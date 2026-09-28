# -*- coding: utf-8 -*-
"""背骨の「横倒し（体の前向き軸まわりの回転）」だけを取り出して、
   平均（常に片側へ傾いている分）を 0 に戻し、揺れ幅を k 倍に弱める。
   前後の曲げ・左右の向き（ひねり）はそのまま。新しい動きは足さない。
   実行: blender -b --factory-startup --python rollfilter.py -- 入力.glb 出力.glb クリップ名 k 骨1,骨2,..."""
import json, struct, sys, math
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,DST,CLIP,K=a[0],a[1],a[2],float(a[3]); BONES=a[4].split(',')
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
def qmul(p,q):
    x1,y1,z1,w1=p; x2,y2,z2,w2=q
    return np.array([w1*x2+x1*w2+y1*z2-z1*y2, w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2, w1*w2-x1*x2-y1*y2-z1*z2])
def qconj(q): return np.array([-q[0],-q[1],-q[2],q[3]])
def rot(q,v): return qmul(qmul(q,np.array([v[0],v[1],v[2],0.0])),qconj(q))[:3]
def qaxis(ax,rad):
    ax=np.array(ax,float); ax=ax/np.linalg.norm(ax); h=rad/2
    return np.array([ax[0]*math.sin(h),ax[1]*math.sin(h),ax[2]*math.sin(h),math.cos(h)])
def slerp(p,q,u):
    d=float(np.dot(p,q))
    if d<0: q=-q; d=-d
    if d>0.9995: r=p+u*(q-p); return r/np.linalg.norm(r)
    th=math.acos(d); s=math.sin(th); return (math.sin((1-u)*th)/s)*p+(math.sin(u*th)/s)*q
order=[]
def walk(i):
    order.append(i)
    for c in nodes[i].get('children',[]): walk(c)
for r in G['scenes'][0]['nodes']: walk(r)
base={i:(np.array(nd.get('translation',[0,0,0]),float),np.array(nd.get('rotation',[0,0,0,1]),float)) for i,nd in enumerate(nodes)}
def chans_of(an):
    out=[]
    for c in an['channels']:
        s=an['samplers'][c['sampler']]; ti=rd(s['input'])[:,0]; vo=rd(s['output'])
        if s.get('interpolation')=='CUBICSPLINE': vo=vo[1::3]
        out.append((c['target']['node'],c['target']['path'],ti,vo))
    return out
def sample(chans,t):
    st={i:(base[i][0].copy(),base[i][1].copy()) for i in base}
    for ni,path,ti,vo in chans:
        x=min(max(t,ti[0]),ti[-1]); k=max(1,min(int(np.searchsorted(ti,x)),len(ti)-1))
        t0,t1=ti[k-1],ti[k]; u=0.0 if t1==t0 else (x-t0)/(t1-t0)
        if path=='rotation': st[ni]=(st[ni][0],slerp(vo[k-1],vo[k],u))
        elif path=='translation': st[ni]=(vo[k-1]+u*(vo[k]-vo[k-1]),st[ni][1])
    return st
def fk(st):
    Wq={}; P={}
    for i in order:
        p=parent.get(i)
        if p is None: Wq[i]=st[i][1]; P[i]=st[i][0].copy()
        else: Wq[i]=qmul(Wq[p],st[i][1]); P[i]=P[p]+rot(Wq[p],st[i][0])
    return Wq,P
Wr,P0=fk({i:base[i] for i in base})
up=P0[n2i['head_end']]-P0[n2i['Hips']]; up/=np.linalg.norm(up)
fwd=P0[n2i['headfront']]-P0[n2i['Head']]; fwd-=up*np.dot(fwd,up); fwd/=np.linalg.norm(fwd)
def twist_angle(D):
    # D（ワールドの回転差）のうち、前向き軸まわりの成分の角度
    v=D[:3]; d=float(np.dot(v,fwd)); w=float(D[3])
    ang=2*math.atan2(d,w)
    if ang>math.pi: ang-=2*math.pi
    if ang<-math.pi: ang+=2*math.pi
    return ang
an=next(x for x in G['animations'] if x.get('name')==CLIP)
T=max(rd(s['input'])[-1,0] for s in an['samplers'])
for bname in BONES:   # 付け根から順に（親を直した後の値で子を計算する）
    b=n2i[bname]
    chans=chans_of(an)
    # 平均の横倒し
    angs=[]
    for k in range(32):
        Wq,_=fk(sample(chans,T*k/32)); D=qmul(Wq[b],qconj(Wr[b])); angs.append(twist_angle(D))
    mean=float(np.mean(angs))
    ch=[c for c in an['channels'] if c['target']['node']==b and c['target']['path']=='rotation']
    for c in ch:
        s=an['samplers'][c['sampler']]; ti=rd(s['input'])[:,0]; v=rd(s['output'])
        step=3 if s.get('interpolation')=='CUBICSPLINE' else 1
        out=v.copy()
        for k in range(1 if step==3 else 0,len(v),step):
            t=ti[k//step]; Wq,_=fk(sample(chans,t))
            Wb=Wq[b]; D=qmul(Wb,qconj(Wr[b])); ang=twist_angle(D)
            newang=K*(ang-mean)
            Wb2=qmul(qaxis(fwd,newang-ang),Wb)       # 前向き軸まわりの分だけ差し替える
            q=qmul(qconj(Wq[parent[b]]),Wb2); out[k]=q/np.linalg.norm(q)
        wr(s['output'],out)
    chans=chans_of(an); angs2=[]
    for k in range(32):
        Wq,_=fk(sample(chans,T*k/32)); angs2.append(twist_angle(qmul(Wq[b],qconj(Wr[b]))))
    print("RF %-8s %-7s 横倒し 平均%+5.1f°(%+5.1f〜%+5.1f) → 平均%+5.1f°(%+5.1f〜%+5.1f)" % (CLIP,bname,math.degrees(mean),math.degrees(min(angs)),math.degrees(max(angs)),math.degrees(np.mean(angs2)),math.degrees(min(angs2)),math.degrees(max(angs2))))
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("RF 書き出し",DST)
