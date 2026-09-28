# -*- coding: utf-8 -*-
"""腕から離れた所（肩掛けの鞄・服の脇）に混ざった腕の重みを外して、胴の骨へ移す。

   わんぱく少女の肩掛け鞄（右の腰）は、自動の骨入れで右腕（上腕・前腕・手）の重みが混ざっていて、
   スキップで腕を振ると鞄が腕に引っ張られて伸びた（2026年9月23日）。
   鞄は体と1つながりのメッシュで、色も同じ緑のベストとほとんど区別できない（色で選ぶとベストへ漏れ、鞄の明るい所が抜けた）。
   そこで色ではなく「腕の骨からの距離」で分ける。
   ・腕の骨の線（肩→肘→手首→手の先）から R 以内の頂点は腕そのものなので触らない
   ・箱の中で、R＋幅 より離れた頂点は、腕の重みを全部外す。その間はなだらかに外す
   ・外した重みは、その頂点に残っている胴の骨（腰・背骨）へ割合どおりに足す。胴の骨が無ければ、
     高さで近い胴の骨（Hips・Spine02・Spine01・Spine）へ振り分ける
   ・同じ位置の頂点（UV の継ぎ目）は同じ重みにする
   glb を直接書き換える（重みだけ）。形・絵・動きは変えない。

   座標は glTF（X 左右・Y 上・Z 前）。キャラの右は −X。
   実行: python armstrip.py 入力.glb 出力.glb 側(Right/Left) "x0,x1,y0,y1,z0,z1" [R 0.045] [幅 0.03]
   箱の上は袖の裾より下にする（袖はゆったりしていて骨から R より遠いので、箱に入ると腕から外れる）。
   例（わんぱく少女の鞄）: ... Right "-0.32,-0.06,0.36,0.55,-0.10,0.26" 0.045 0.03"""
import json, struct, sys
import numpy as np

a = [x for x in sys.argv[1:]]
if '--' in a: a = a[a.index('--') + 1:]
SRC, DST, SIDE = a[0], a[1], a[2]
X0, X1, Y0, Y1, Z0, Z1 = [float(v) for v in a[3].split(',')]
R = float(a[4]) if len(a) > 4 else 0.045
BAND = float(a[5]) if len(a) > 5 else 0.03

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0] + Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO + BL])
DT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NUM = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
def view(i):
    ac = G['accessors'][i]; bv = G['bufferViews'][ac['bufferView']]
    n = NUM[ac['type']]; dt = np.dtype(DT[ac['componentType']])
    return ac, n, dt, bv.get('byteOffset', 0) + ac.get('byteOffset', 0), bv.get('byteStride') or n * dt.itemsize
def rd(i):
    ac, n, dt, b, st = view(i); out = np.empty((ac['count'], n), dt)
    for k in range(n): out[:, k] = np.ndarray((ac['count'],), dt, bd, b + k * dt.itemsize, (st,))
    return out
def wr(i, arr):
    ac, n, dt, b, st = view(i)
    for k in range(n): np.ndarray((ac['count'],), dt, bd, b + k * dt.itemsize, (st,))[:] = arr[:, k]

sk = G['skins'][0]; names = [G['nodes'][j].get('name') for j in sk['joints']]
IBM = rd(sk['inverseBindMatrices']).astype(float).reshape(-1, 4, 4).transpose(0, 2, 1)
JP = {n: np.linalg.inv(IBM[k])[:3, 3] for k, n in enumerate(names)}
ARMS = [k for k, n in enumerate(names) if n in (SIDE + 'Shoulder', SIDE + 'Arm', SIDE + 'ForeArm', SIDE + 'Hand')]
TRUNK = [n for n in ('Hips', 'Spine02', 'Spine01', 'Spine') if n in names]
TRK = [names.index(n) for n in TRUNK]
pa, pf, ph = JP[SIDE + 'Arm'], JP[SIDE + 'ForeArm'], JP[SIDE + 'Hand']
tip = ph + (ph - pf) * 1.0                       # 手の先（手首から前腕と同じ長さ。6割だと指先が外れた）
segs = [(pa, pf), (pf, ph), (ph, tip)]
def segdist(P, s0, s1):
    v = s1 - s0; t = np.clip(((P - s0) @ v) / (v @ v), 0, 1)
    return np.linalg.norm(P - (s0 + t[:, None] * v), axis=1)

cands = [(G['accessors'][m['primitives'][0]['attributes']['POSITION']]['count'], i)
         for i, m in enumerate(G['meshes']) if 'JOINTS_0' in m['primitives'][0]['attributes']]
pr = G['meshes'][max(cands)[1]]['primitives'][0]
P = rd(pr['attributes']['POSITION']).astype(float)
J = rd(pr['attributes']['JOINTS_0']).astype(np.int64)
wac = G['accessors'][pr['attributes']['WEIGHTS_0']]
Wraw = rd(pr['attributes']['WEIGHTS_0'])
WMAX = 1.0 if wac['componentType'] == 5126 else float(np.iinfo(DT[wac['componentType']]).max)
W = Wraw.astype(float) / WMAX

d = np.min(np.stack([segdist(P, s0, s1) for s0, s1 in segs]), 0)
box = (P[:, 0] >= X0) & (P[:, 0] <= X1) & (P[:, 1] >= Y0) & (P[:, 1] <= Y1) & (P[:, 2] >= Z0) & (P[:, 2] <= Z1)
t = np.clip((d - R) / BAND, 0, 1); f = np.where(box, t * t * (3 - 2 * t), 0.0)   # 外す割合
armw = np.zeros(len(P))
for k in ARMS: armw += np.where(np.isin(J, [k]), W, 0).sum(1)
tgt = (f > 0) & (armw > 1e-4)
print("AS 箱の中 %d 頂点、腕から離れていて腕の重みがある %d 頂点（外す前の腕の重み 合計 %.1f）" % (int(box.sum()), int(tgt.sum()), float((armw * f)[tgt].sum())))

ty = np.array([JP[n][1] for n in TRUNK])
for vi in np.nonzero(tgt)[0]:
    acc = {}
    for k in range(J.shape[1]):
        if W[vi, k] > 0: acc[int(J[vi, k])] = acc.get(int(J[vi, k]), 0.0) + W[vi, k]
    moved = 0.0
    for k in ARMS:
        if k in acc:
            m = acc[k] * f[vi]; acc[k] -= m; moved += m
    trunk_here = {k: acc[k] for k in TRK if acc.get(k, 0) > 0}
    if trunk_here:
        s = sum(trunk_here.values())
        for k, w in trunk_here.items(): acc[k] += moved * w / s
    else:
        # 高さで近い胴の骨2本へ
        y = P[vi, 1]; o = np.argsort(np.abs(ty - y))[:2]
        dd = np.abs(ty[o] - y) + 1e-6; ww = (1 / dd) / (1 / dd).sum()
        for oi, w in zip(o, ww): acc[TRK[oi]] = acc.get(TRK[oi], 0.0) + moved * w
    top = sorted(acc.items(), key=lambda x: -x[1])[:J.shape[1]]
    s = sum(w for _, w in top) or 1.0
    J[vi] = 0; W[vi] = 0
    for k, (j, w) in enumerate(top): J[vi, k] = j; W[vi, k] = w / s

# 同じ位置の頂点は同じ重みに（最初に出てきた頂点に合わせる）
key = np.round(P / 1e-5).astype(np.int64)
_, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True); inv = inv.ravel()
ch = tgt | tgt[first[inv]]
J[ch] = J[first[inv]][ch]; W[ch] = W[first[inv]][ch]

armw2 = np.zeros(len(P))
for k in ARMS: armw2 += np.where(np.isin(J, [k]), W, 0).sum(1)
print("AS 外した後の腕の重み 合計 %.1f（箱の中で腕から R＋幅 より離れた頂点の最大 %.3f）" % (float(armw2[tgt].sum()), float(armw2[box & (d > R + BAND)].max() if (box & (d > R + BAND)).any() else 0)))
if WMAX == 1.0: Wout = W.astype(np.float32)
else:
    Wout = np.round(W * WMAX).astype(np.int64); Wout[:, 0] += int(WMAX) - Wout.sum(1)
wr(pr['attributes']['JOINTS_0'], J); wr(pr['attributes']['WEIGHTS_0'], Wout)

js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
bn = bytes(bd); bn += b'\x00' * ((4 - len(bn) % 4) % 4)
out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
open(DST, 'wb').write(out)
print("AS 書き出し", DST)
