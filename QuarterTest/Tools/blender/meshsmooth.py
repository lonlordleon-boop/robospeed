# -*- coding: utf-8 -*-
"""メッシュ表面の細かいうねりをならす（光を当てたときに出る、ひび割れのような筋を消すため）。
   ふつうの平均化だけだと形が痩せるので、縮める手と膨らませる手を交互にかける（タウビン法）。
   UV の継ぎ目で分かれている同じ位置の頂点はいっしょに動かす（割れ目ができないように）。
   実行: blender -b --factory-startup -P meshsmooth.py -- 入力.glb 出力.glb 回数 [守る帯]
   守る帯は「下限,上限」を ; でつないで複数書ける。例: 0.58,1.30;0.00,0.16
   顔をならすと、彫り込まれた目の形がつぶれて絵が崩れるので、頭は守ること。
   動かす箱（5番目）を「x下限,x上限,y下限,y上限,z下限,z上限」（glTF の座標、Y が上・Z が前）で書くと、
   その箱の中の頂点だけをならす。目と口を絵で貼る顔（のっぺらぼうから作ったキャラ）は形を守る必要がないので、
   顔の前面だけを箱で囲んでならす。守る帯が要らなければ4番目は "" にする。
   例: ... -- in.glb out.glb 10 "" -0.17,0.17,0.64,0.90,0.15,0.60"""
import json, struct, sys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
ITER = int(a[2])
# 守る帯は「下限,上限」を ; で区切って複数指定できる
KEEP = [[float(x) for x in b.split(',')] for b in a[3].split(';')] if len(a) > 3 and a[3] else None
# 動かす箱（これを指定したら、箱の外はすべて動かさない）
MOVE = [float(x) for x in a[4].split(',')] if len(a) > 4 and a[4] else None
LAM, MU = 0.50, -0.53

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
rep = np.zeros((ng, 3))
for v in range(nv): rep[grp[v]] = P[v]

nb = [set() for _ in range(ng)]
for t in range(0, len(idx), 3):
    g = [grp[idx[t]], grp[idx[t+1]], grp[idx[t+2]]]
    for i in range(3):
        for j in range(3):
            if i != j: nb[g[i]].add(g[j])
nbl = [np.array(sorted(s), dtype=int) for s in nb]

frozen = np.zeros(ng, bool)
if KEEP is not None:
    for lo, hi in KEEP:
        frozen |= (rep[:,1] >= lo) & (rep[:,1] <= hi)        # glTF は Y が上
    print("MS 動かさない頂点 %d（守る帯 %s）" % (int(frozen.sum()), KEEP))
if MOVE is not None:
    x0, x1, y0, y1, z0, z1 = MOVE
    inside = ((rep[:,0] >= x0) & (rep[:,0] <= x1) & (rep[:,1] >= y0) & (rep[:,1] <= y1) &
              (rep[:,2] >= z0) & (rep[:,2] <= z1))
    frozen |= ~inside
    print("MS 動かす頂点 %d（箱 %s）" % (int((~frozen).sum()), MOVE))

Q = rep.copy()
def step(Q, w):
    R = Q.copy()
    for g in range(ng):
        if frozen[g] or len(nbl[g]) == 0: continue
        R[g] = Q[g] + w*(Q[nbl[g]].mean(0) - Q[g])
    return R
for it in range(ITER):
    Q = step(Q, LAM)
    Q = step(Q, MU)
d = np.linalg.norm(Q - rep, axis=1)
print("MS ならし %d 回、動いた量 平均%.5f 最大%.5f" % (ITER, d.mean(), d.max()))

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
    N2 = np.array([acc[grp[v]] for v in range(nv)])
    wr(pr['attributes']['NORMAL'], N2)
    print("MS 法線を計算し直した")

js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out)
print("MS 書き出し", DST)
