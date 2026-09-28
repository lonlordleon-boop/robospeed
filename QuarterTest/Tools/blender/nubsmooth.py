# -*- coding: utf-8 -*-
"""指定した球の中だけを、まわりの面になじむようにならす（生成時にできた小さな突起を消す）。
   突起は細いので、隣の頂点の平均へ寄せるのを繰り返すと、まわりの面に吸い込まれて消える。
   UV の継ぎ目で分かれている同じ位置の頂点は、いっしょに動かす（割れ目ができないように）。
   実行: blender -b --factory-startup --python nubsmooth.py -- 入力.glb 出力.glb x,y,z 半径 回数"""
import json, struct, sys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
CEN = np.array([float(x) for x in a[2].split(',')])
RAD = float(a[3])
ITER = int(a[4]) if len(a) > 4 else 12

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO+BL])
COMP = {5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
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

# 同じ位置の頂点をひとまとめにする（UV の継ぎ目で分かれているものを溶接）
key = {}
group = np.zeros(nv, int)
for v in range(nv):
    k = tuple(np.round(P[v], 6))
    if k not in key: key[k] = len(key)
    group[v] = key[k]
ng = len(key)
rep = np.zeros((ng, 3))
for v in range(nv): rep[group[v]] = P[v]

# まとまり同士のつながり
nb = [set() for _ in range(ng)]
for t in range(0, len(idx), 3):
    g = [group[idx[t]], group[idx[t+1]], group[idx[t+2]]]
    for i in range(3):
        for j in range(3):
            if i != j: nb[g[i]].add(g[j])

d = np.linalg.norm(rep - CEN, axis=1)
inside = np.where(d < RAD)[0]
# ふちほど動かさない（急な段差ができないように）
t = np.clip(1.0 - d[inside]/RAD, 0.0, 1.0)
amt = t*t*(3-2*t)
print("NS 球の中のまとまり %d 個（全 %d）" % (len(inside), ng))

Q = rep.copy()
for it in range(ITER):
    Nw = Q.copy()
    for i, g in enumerate(inside):
        ns = list(nb[g])
        if not ns: continue
        Nw[g] = Q[g] + amt[i]*(Q[ns].mean(0) - Q[g])
    Q = Nw
moved = np.linalg.norm(Q[inside]-rep[inside], axis=1)
print("NS 動かした量 最大%.4f 平均%.4f" % (moved.max() if len(moved) else 0, moved.mean() if len(moved) else 0))

P2 = P.copy()
for v in range(nv): P2[v] = Q[group[v]]
wr(pr['attributes']['POSITION'], P2)
ac = G['accessors'][pr['attributes']['POSITION']]
ac['min'] = P2.min(0).tolist(); ac['max'] = P2.max(0).tolist()

# 動かしたところの法線を、まわりの面から計算し直す
if N is not None:
    touched = set()
    for i, g in enumerate(inside):
        if moved[i] > 1e-6: touched.add(g)
    acc = np.zeros((nv, 3))
    for t3 in range(0, len(idx), 3):
        a_, b_, c_ = idx[t3], idx[t3+1], idx[t3+2]
        if not (group[a_] in touched or group[b_] in touched or group[c_] in touched): continue
        fn = np.cross(P2[b_]-P2[a_], P2[c_]-P2[a_])
        acc[a_] += fn; acc[b_] += fn; acc[c_] += fn
    N2 = N.copy(); fixed = 0
    for v in range(nv):
        if group[v] in touched:
            l = np.linalg.norm(acc[v])
            if l > 1e-12: N2[v] = acc[v]/l; fixed += 1
    wr(pr['attributes']['NORMAL'], N2)
    print("NS 法線を計算し直した頂点 %d 個" % fixed)

js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out)
print("NS 書き出し", DST)
