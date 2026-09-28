# -*- coding: utf-8 -*-
"""腕を前後に振る回転を、指定したクリップ（または全部）に焼き込む。
   骨の位置をずらすだけではアニメの回転に打ち消されるため。
   メッシュは触らないので結び直しはそのまま。

   spread_arms.py は前を向く軸のまわりに回して腕を「横へ開く」。
   こちらは横向きの軸のまわりに回して腕を「前後へ振る」。左右どちらか片方だけも指定できる。

   生成したアニメには、片腕だけが後ろへ流れたまま止まっているものがある。
   girl_v55 の Idle がそれで、右手が左手より常に4〜11cm 後ろにあった。
   歩きのように左右が交互に入れ替わるものは正常なので、そちらには掛けないこと。

   実行: blender -b --factory-startup --python swingarm.py -- 入力.glb 出力.glb 角度 [L|R|LR 既定LR] [クリップ名,...]
   角度は正で前。クリップ名を省くと素の姿勢と全クリップに掛かる。"""
import json, struct, sys, math, os
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, DEG = a[0], a[1], float(a[2])
SIDE = (a[3].upper() if len(a) > 3 and a[3] else 'LR')   # L / R / LR
# 5つ目の引数があれば、そのクリップ（カンマ区切り）だけに回転を焼き込む。
ONLY = set(a[4].split(',')) if len(a) > 4 and a[4] else None

raw = open(SRC,'rb').read(); off=12; ck=[]
while off < len(raw):
    ln,ty = struct.unpack_from('<II', raw, off); off+=8; ck.append((ty,off,ln)); off+=ln
Jm = {t:(o,l) for t,o,l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO,BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO+BL])

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
def qmul(a,b):
    ax,ay,az,aw=a; bx,by,bz,bw=b
    return np.array([aw*bx+ax*bw+ay*bz-az*by,
                     aw*by-ax*bz+ay*bw+az*bx,
                     aw*bz+ax*by-ay*bx+az*bw,
                     aw*bw-ax*bx-ay*by-az*bz])
def qconj(q): return np.array([-q[0],-q[1],-q[2],q[3]])
def qaxis(axis, deg):
    ax=np.array(axis,float); ax=ax/np.linalg.norm(ax)
    h=math.radians(deg)/2.0
    return np.array([ax[0]*math.sin(h), ax[1]*math.sin(h), ax[2]*math.sin(h), math.cos(h)])
def worldQ(i):
    q=np.array([0,0,0,1.0]); ch=[]; j=i
    while j is not None: ch.append(j); j=parent.get(j)
    for j in reversed(ch):
        q=qmul(q, np.array(nodes[j].get('rotation',[0,0,0,1]),float))
    return q

# 前がどちらかを頭の目印の骨から決める
def worldPos(i):
    M=np.eye(4); ch=[]; j=i
    while j is not None: ch.append(j); j=parent.get(j)
    for j in reversed(ch):
        nd=nodes[j]; L=np.eye(4)
        L[:3,:3]=q2m(np.array(nd.get('rotation',[0,0,0,1]),float))@np.diag(np.array(nd.get('scale',[1,1,1]),float))
        L[:3,3]=np.array(nd.get('translation',[0,0,0]),float); M=M@L
    return M[:3,3]
fwd = worldPos(n2i['headfront']) - worldPos(n2i['Head'])
fwd[1]=0.0; fwd = fwd/np.linalg.norm(fwd)
print("FRONT", [round(v,3) for v in fwd])

# 親（腰）の向きを使って、ワールドの回転を骨のローカルに移す
# 前後の振りは左右いっしょに同じ向きへ回すので、符号は分けない
targets = {}
if 'L' in SIDE: targets['LeftArm'] = 1.0
if 'R' in SIDE: targets['RightArm'] = 1.0
Ms = {}
for name, sign in targets.items():
    i = n2i[name]
    Rp = worldQ(parent[i])
    # 横向きの軸＝前を向く軸と上下の軸に直角。この軸のまわりで腕が前後に振れる
    up = np.array([0.0, 1.0, 0.0])          # glTF の中は Y が上
    sx = np.cross(up, fwd); sx = sx/np.linalg.norm(sx)
    W  = qaxis(sx, -sign*DEG)               # 正で前へ
    Ms[i] = qmul(qmul(qconj(Rp), W), Rp)    # 親の座標系へ移す

# 素の姿勢（腕）。クリップ限定のときは素の姿勢には触らない
if ONLY is None:
    for i, M in Ms.items():
        q = np.array(nodes[i].get('rotation',[0,0,0,1]),float)
        nodes[i]['rotation'] = qmul(M, q).tolist()

# アニメのカーブ
patched = 0
for an in G['animations']:
    if ONLY is not None and an.get('name') not in ONLY: continue
    for chn in an['channels']:
        tg = chn['target']
        if tg['path'] != 'rotation': continue
        ni = tg.get('node')
        if ni not in Ms: continue
        smp = an['samplers'][chn['sampler']]
        v = rd(smp['output'])
        step = 3 if smp.get('interpolation') == 'CUBICSPLINE' else 1
        out = v.copy()
        for k in range(len(v)):
            out[k] = qmul(Ms[ni], v[k])
            out[k] = out[k] / np.linalg.norm(out[k])
        wr(smp['output'], out)
        patched += 1

js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))
out+=struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out)
print("SWING", DEG, "度", SIDE, " 直したカーブ", patched, "本 →", DST, os.path.getsize(DST))
