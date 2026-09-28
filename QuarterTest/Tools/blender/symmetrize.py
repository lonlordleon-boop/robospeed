# -*- coding: utf-8 -*-
"""片足を引きずる歩きを直す：良い方の半周期を左右反転して一周期に組み直す。
   腰の左右の片寄りは平均を引いて中心に戻す。回転の捏造はしない（既存の動きの鏡写し）。
   実行: blender -b --factory-startup --python symmetrize.py -- 入力.glb 出力.glb クリップ名"""
import json, struct, sys, math
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,DST,CLIP=a[0],a[1],a[2]
raw=open(SRC,'rb').read(); off=12; ck=[]
while off<len(raw):
    ln,ty=struct.unpack_from('<II',raw,off); off+=8; ck.append((ty,off,ln)); off+=ln
Jm={t:(o,l) for t,o,l in ck}
G=json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO,BL=Jm[0x004E4942]; bd=bytearray(raw[BO:BO+BL])
COMP={5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def rd(i):
    ac=G['accessors'][i]; n=NUM[ac['type']]; f,s=COMP[ac['componentType']]
    bv=G['bufferViews'][ac['bufferView']]; b=bv.get('byteOffset',0)+ac.get('byteOffset',0); st=bv.get('byteStride') or n*s
    return np.array([struct.unpack_from('<'+f*n,bd,b+k*st) for k in range(ac['count'])],float)
nodes=G['nodes']; parent={}
for i,nd in enumerate(nodes):
    for c in nd.get('children',[]): parent[c]=i
n2i={nd.get('name',''):i for i,nd in enumerate(nodes)}
def qmul(p,q):
    x1,y1,z1,w1=p; x2,y2,z2,w2=q
    return np.array([w1*x2+x1*w2+y1*z2-z1*y2, w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2, w1*w2-x1*x2-y1*y2-z1*z2])
def qconj(q): return np.array([-q[0],-q[1],-q[2],q[3]])
def slerp(p,q,u):
    d=float(np.dot(p,q))
    if d<0: q=-q; d=-d
    if d>0.9995: r=p+u*(q-p); return r/np.linalg.norm(r)
    th=math.acos(d); s=math.sin(th); return (math.sin((1-u)*th)/s)*p+(math.sin(u*th)/s)*q
an=next(x for x in G['animations'] if x.get('name')==CLIP)
base={i:(np.array(nd.get('translation',[0,0,0]),float),np.array(nd.get('rotation',[0,0,0,1]),float)) for i,nd in enumerate(nodes)}
chans=[]
for c in an['channels']:
    s=an['samplers'][c['sampler']]; ti=rd(s['input'])[:,0]; vo=rd(s['output'])
    if s.get('interpolation')=='CUBICSPLINE': vo=vo[1::3]
    chans.append((c['target']['node'],c['target']['path'],ti,vo))
T=max(ti[-1] for _,_,ti,_ in chans)
def sample(t):
    st={i:(base[i][0].copy(),base[i][1].copy()) for i in base}
    for ni,path,ti,vo in chans:
        x=min(max(t,ti[0]),ti[-1]); k=max(1,min(int(np.searchsorted(ti,x)),len(ti)-1))
        t0,t1=ti[k-1],ti[k]; u=0.0 if t1==t0 else (x-t0)/(t1-t0)
        if path=='rotation': st[ni]=(st[ni][0],slerp(vo[k-1],vo[k],u))
        elif path=='translation': st[ni]=(vo[k-1]+u*(vo[k]-vo[k-1]),st[ni][1])
    return st
# 階層順（親→子）
order=[]
def walk(i):
    order.append(i)
    for c in nodes[i].get('children',[]): walk(c)
for r in G['scenes'][0]['nodes']: walk(r)
def worldQ(st):
    W={}
    for i in order:
        W[i]=st[i][1] if parent.get(i) is None else qmul(W[parent[i]],st[i][1])
    return W
def worldP(st):
    Wq=worldQ(st); P={}
    def rot(q,v):
        return qmul(qmul(q,np.array([v[0],v[1],v[2],0.0])),qconj(q))[:3]
    for i in order:
        p=parent.get(i)
        P[i]=st[i][0].copy() if p is None else P[p]+rot(Wq[p],st[i][0])
    return P
mirror_name=lambda n: n.replace('Left','@@').replace('Right','Left').replace('@@','Right')
mirror={i:n2i.get(mirror_name(nodes[i].get('name','')),i) for i in range(len(nodes))}
def M(q): return np.array([q[0],-q[1],-q[2],q[3]])   # X面で鏡写し
# 左足が一番高い時刻を中心に半周期を取る
N=48; ts=[T*k/N for k in range(N)]
lf=n2i['LeftFoot']
hs=[worldP(sample(t))[lf][1] for t in ts]
tpk=ts[int(np.argmax(hs))]; t0=(tpk-T/4)%T
print("SYM 周期%.3f 左足最高%.3f 半周期の開始%.3f"%(T,tpk,t0))
NEW=48; frames=[]
for k in range(NEW):
    u=k/NEW
    if u<0.5: st=sample((t0+u*T)%T); Wq=worldQ(st); loc={i:st[i] for i in st}
    else:
        st=sample((t0+(u-0.5)*T)%T); Wq=worldQ(st)
        # 鏡写し：各骨のワールド回転を M で反転し、鏡の相手の骨に与える
        Wm={mirror[i]:M(Wq[i]) for i in order}
        loc={}
        for i in order:
            p=parent.get(i)
            q=Wm[i] if p is None else qmul(qconj(Wm[p]),Wm[i])
            tr=base[i][0].copy()
            if nodes[i].get('name')=='Hips':
                th=st[n2i['Hips']][0]; tr=np.array([-th[0],th[1],th[2]])
            loc[i]=(tr,q/np.linalg.norm(q))
    frames.append(loc)
# 腰の左右の平均を引いて中心へ
hx=np.mean([f[n2i['Hips']][0][0] for f in frames]) - base[n2i['Hips']][0][0]
for f in frames:
    t=f[n2i['Hips']][0]; f[n2i['Hips']]=(np.array([t[0]-hx,t[1],t[2]]),f[n2i['Hips']][1])
print("SYM 腰の片寄りを %.4f 戻した"%hx)
# 書き出し：回転は全骨、移動は Hips のみ。滑らかに繋がるよう最後に先頭を複製
times=[T*k/NEW for k in range(NEW)]+[T]
def add_acc(arr,ctype,is_time=False):
    global bd
    while len(bd)%4: bd.append(0)
    o=len(bd); n=NUM[ctype]
    for row in arr: bd+=struct.pack('<'+'f'*n,*([row] if n==1 else list(row)))
    G['bufferViews'].append({'buffer':0,'byteOffset':o,'byteLength':len(bd)-o})
    acc={'bufferView':len(G['bufferViews'])-1,'componentType':5126,'count':len(arr),'type':ctype}
    if is_time: acc['min']=[float(min(arr))]; acc['max']=[float(max(arr))]
    G['accessors'].append(acc); return len(G['accessors'])-1
ti_acc=add_acc(times,'SCALAR',True)
samplers=[]; channels=[]
animated=set(ni for ni,_,_,_ in chans)
for i in order:
    if i not in animated: continue
    qs=[f[i][1] for f in frames]
    # 連続性：符号を揃える
    for k in range(1,len(qs)):
        if np.dot(qs[k],qs[k-1])<0: qs[k]=-qs[k]
    qs=qs+[qs[0]]
    samplers.append({'input':ti_acc,'output':add_acc(qs,'VEC4'),'interpolation':'LINEAR'})
    channels.append({'sampler':len(samplers)-1,'target':{'node':i,'path':'rotation'}})
    if nodes[i].get('name')=='Hips':
        tr=[f[i][0] for f in frames]; tr=tr+[tr[0]]
        samplers.append({'input':ti_acc,'output':add_acc(tr,'VEC3'),'interpolation':'LINEAR'})
        channels.append({'sampler':len(samplers)-1,'target':{'node':i,'path':'translation'}})
an['samplers']=samplers; an['channels']=channels
G['buffers'][0]['byteLength']=len(bd)
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd)+b'\x00'*((4-len(bd)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("SYM 書き出し",DST)
