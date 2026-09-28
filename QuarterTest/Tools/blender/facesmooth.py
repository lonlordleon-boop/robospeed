# -*- coding: utf-8 -*-
"""顔の前面の形を、正面から見た「出っぱりの地図」としてぼかす（のっぺらぼうから作ったキャラ用）。

   生成された顔には、細かいでこぼこと、つまんだように尖った鼻がある。
   鼻の先は 1mm 間隔の小さな頂点が27個も集まってできていて、meshsmooth.py（隣の頂点との平均）では
   15回かけてもほとんど動かなかった。

   そこで、顔の前面の頂点を (x, 高さ y) の平面に並べ、前後の出っぱり z だけを
   まわりの頂点の z とガウスの重みで平均する。x と y は動かさないので、正面から見た輪郭は変わらない。
   尖った鼻は丸いふくらみになり、でこぼこは平らになる。
   目と口は絵で貼るので、形をならしても絵は崩れない（彫り込まれた目の顔には使わないこと）。

   箱のふちの 2cm でぼかしを弱め、箱の外との段差を作らない。
   glTF の座標（Y が上、Z が前）で指定する。UV の継ぎ目で分かれた同じ位置の頂点はいっしょに動かす。

   実行: blender -b --factory-startup -P facesmooth.py --
         入力.glb 出力.glb "x下限,x上限,y下限,y上限,z下限" ぼかしの幅σ(m) [強さ 0〜1 既定1] [z か n 既定z]
   例:   ... -- in.glb out.glb -0.17,0.17,0.64,0.90,0.12 0.012
"""
import json, struct, sys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
X0, X1, Y0, Y1, Z0 = [float(v) for v in a[2].split(',')]
SIG = float(a[3])
AMT = float(a[4]) if len(a) > 4 and a[4] else 1.0
# n を渡すと形は動かさず、面の向き（法線）だけをぼかす。
# 顔の前面は頂点が 228 個しかなく粗いので、形をぼかすと大きな面の角ばりが出た。
# 光で見えるでこぼこは法線で決まるので、法線だけならせば輪郭も絵も変えずに肌がなめらかに見える
MODE = a[5] if len(a) > 5 else 'z'

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO+BL])
COMP = {5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}
def lay(i):
    ac = G['accessors'][i]; n = NUM[ac['type']]; f, s = COMP[ac['componentType']]
    bv = G['bufferViews'][ac['bufferView']]
    return ac, n, f, bv.get('byteOffset',0)+ac.get('byteOffset',0), bv.get('byteStride') or n*s
def rd(i):
    ac, n, f, b, st = lay(i)
    return np.array([struct.unpack_from('<'+f*n, bd, b+k*st) for k in range(ac['count'])], float)
def wr(i, arr):
    ac, n, f, b, st = lay(i)
    for k in range(ac['count']): struct.pack_into('<'+f*n, bd, b+k*st, *arr[k])

pr = G['meshes'][0]['primitives'][0]
P = rd(pr['attributes']['POSITION'])
N = rd(pr['attributes']['NORMAL']) if 'NORMAL' in pr['attributes'] else None
idx = rd(pr['indices']).astype(int)[:, 0]
nv = len(P)

# 同じ位置の頂点をひとまとめにする
key = {}; grp = np.zeros(nv, int)
for v in range(nv):
    k = tuple(np.round(P[v], 6))
    if k not in key: key[k] = len(key)
    grp[v] = key[k]
ng = len(key)
rep = np.zeros((ng, 3)); nrm = np.zeros((ng, 3))
for v in range(nv):
    rep[grp[v]] = P[v]
    if N is not None: nrm[grp[v]] += N[v]

# 顔の前面: 箱の中で、前を向いている点
inbox = (rep[:,0] >= X0) & (rep[:,0] <= X1) & (rep[:,1] >= Y0) & (rep[:,1] <= Y1) & (rep[:,2] >= Z0)
nl = np.linalg.norm(nrm, axis=1); nl[nl < 1e-12] = 1
front = inbox & ((nrm[:,2] / nl) > 0.3) if N is not None else inbox
sel = np.nonzero(front)[0]
print("FS 顔の前面の点 %d（箱の中 %d）" % (len(sel), int(inbox.sum())))

XY = rep[sel][:, :2]; Z = rep[sel][:, 2]

if MODE == 'n':
    # 法線だけぼかす。同じ位置の頂点の法線を足した向きをガウスで平均し、箱のふちで元の向きへ戻す
    NU = nrm[sel] / nl[sel][:, None]
    R = 3 * SIG
    NS = np.zeros_like(NU)
    for k in range(len(sel)):
        d2 = ((XY - XY[k])**2).sum(1)
        m = d2 < R*R
        w = np.exp(-0.5 * d2[m] / (SIG*SIG))
        v = (NU[m] * w[:, None]).sum(0); NS[k] = v / np.linalg.norm(v)
    edge = np.minimum.reduce([XY[:,0]-X0, X1-XY[:,0], XY[:,1]-Y0, Y1-XY[:,1]])
    fall = (np.clip(edge / 0.02, 0, 1) * AMT)[:, None]
    NF = NU * (1 - fall) + NS * fall
    NF /= np.linalg.norm(NF, axis=1)[:, None]
    ang = np.degrees(np.arccos(np.clip((NF * NU).sum(1), -1, 1)))
    print("FS 法線の向きの変化 平均 %.1f度 最大 %.1f度" % (ang.mean(), ang.max()))
    gmap = {g: k for k, g in enumerate(sel)}
    N2 = N.copy()
    for v in range(nv):
        k = gmap.get(grp[v])
        if k is not None: N2[v] = NF[k]
    wr(pr['attributes']['NORMAL'], N2)
    js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
    bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
    out = b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
    open(DST,'wb').write(out)
    print("FS 書き出し（法線だけ）", DST)
    sys.exit(0)
Znew = Z.copy()
R = 3 * SIG
for k in range(len(sel)):
    d2 = ((XY - XY[k])**2).sum(1)
    m = d2 < R*R
    w = np.exp(-0.5 * d2[m] / (SIG*SIG))
    Znew[k] = (w * Z[m]).sum() / w.sum()
# 箱のふち 2cm でぼかしを弱める
edge = np.minimum.reduce([XY[:,0]-X0, X1-XY[:,0], XY[:,1]-Y0, Y1-XY[:,1]])
fall = np.clip(edge / 0.02, 0, 1) * AMT
dz = (Znew - Z) * fall
print("FS 前後の動き 平均 %.2fmm 最大 %.2fmm（へこませる向き 最大 %.2fmm）" % (np.abs(dz).mean()*1000, np.abs(dz).max()*1000, -dz.min()*1000))
Q = rep.copy(); Q[sel, 2] += dz

P2 = P.copy()
for v in range(nv): P2[v] = Q[grp[v]]
wr(pr['attributes']['POSITION'], P2)
ac = G['accessors'][pr['attributes']['POSITION']]
ac['min'] = P2.min(0).tolist(); ac['max'] = P2.max(0).tolist()

# 法線を計算し直す（同じ位置の頂点は同じ向きにそろえる）
if N is not None:
    acc = np.zeros((ng, 3))
    for t in range(0, len(idx), 3):
        a_, b_, c_ = idx[t], idx[t+1], idx[t+2]
        fn = np.cross(P2[b_]-P2[a_], P2[c_]-P2[a_])
        acc[grp[a_]] += fn; acc[grp[b_]] += fn; acc[grp[c_]] += fn
    ln_ = np.linalg.norm(acc, axis=1); ln_[ln_ < 1e-12] = 1.0
    acc = acc / ln_[:, None]
    wr(pr['attributes']['NORMAL'], np.array([acc[grp[v]] for v in range(nv)]))

js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out)
print("FS 書き出し", DST)
