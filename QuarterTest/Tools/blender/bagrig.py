# -*- coding: utf-8 -*-
"""腰に下げた鞄が、腕や脚に引っ張られないようにする（重みだけ書き換える）。

   わんぱく少女の肩掛け鞄（右の腰）は、自動の骨入れで右腕と右脚の重みが混ざっていて、
   スキップで腕を振ると鞄が伸び、脚を上げると鞄の角がとがって飛び出した（2026年9月23日）。
   鞄は体と1つながりのメッシュで、UV の島も細かく割れているので、形では選べない。
   armstrip.py（腕の骨からの距離で分ける）だけでは、腕のすぐ横のベストが腕に付いたまま残り、
   腕を振るとベストが腕と鞄の間に薄く引き伸ばされた。そこで絵の色で3つに分ける。
   ・腕の骨から 5.5cm 以内の肌（腕・手）と、上腕から 9cm 以内の白（袖）: 触らない
   ・短パン（明るいベージュ）: 腕の重みだけ外す（脚といっしょに動く必要がある）
   ・それ以外（鞄・ベスト・肩ひも）: 腕と脚の重みを外して、胴の骨（腰・背骨）だけにする
   色の判定は、同じ位置の頂点の平均色で行い、まわりの頂点との多数決を2回かけて、しわの暗い所などの誤判定をならす。
   外す割合は、まわりとの平均で段々にならしてから掛ける（境目で面が裂けないように）。
   箱のふちでは外す割合を 0 へ戻す。外した重みは、その頂点に残っている胴の骨へ割合どおりに、
   胴の骨が無ければ高さの近い胴の骨2本へ足す。

   色の目安（わんぱく少女）: 肌 色相 0.06・明度 0.96〜1.0、短パン 色相 0.11・明度 0.67、鞄 明度 0.29、ベスト 明度 0.47
   座標は glTF（X 左右・Y 上・Z 前）。キャラの右は −X。
   実行: python bagrig.py 入力.glb 出力.glb 側(Right/Left) "x0,x1,y0,y1,z0,z1" [ならす回数 3]
         （blender -b --factory-startup --python-expr から呼ぶ。絵を読むのに bpy を使う）
   例（わんぱく少女の鞄）: ... Right "-0.33,-0.05,0.38,0.54,-0.14,0.32" 3
   箱のふち（各辺の 15%）では外す割合を弱めるので、鞄より一回り大きく取る（鞄の外の端がふちにかかると、そこだけ脚に残った）。
   箱の上は袖の裾より下にする（0.57 にしたら袖が腕から外れて、腕を振ると白い布が引き伸ばされた）。"""
import json, struct, sys, os, tempfile, colorsys
import numpy as np
import bpy

a = [x for x in sys.argv[1:]]
if '--' in a: a = a[a.index('--') + 1:]
SRC, DST, SIDE = a[0], a[1], a[2]
X0, X1, Y0, Y1, Z0, Z1 = [float(v) for v in a[3].split(',')]
SMO = int(a[4]) if len(a) > 4 else 3

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
LEGS = [k for k, n in enumerate(names) if n in (SIDE + 'UpLeg', SIDE + 'Leg')]
TRUNK = [n for n in ('Hips', 'Spine02', 'Spine01', 'Spine') if n in names]
TRK = [names.index(n) for n in TRUNK]; ty = np.array([JP[n][1] for n in TRUNK])

cands = [(G['accessors'][m['primitives'][0]['attributes']['POSITION']]['count'], i)
         for i, m in enumerate(G['meshes']) if 'JOINTS_0' in m['primitives'][0]['attributes']]
pr = G['meshes'][max(cands)[1]]['primitives'][0]
P = rd(pr['attributes']['POSITION']).astype(float); UV = rd(pr['attributes']['TEXCOORD_0']).astype(float)
T = rd(pr['indices']).astype(np.int64).reshape(-1, 3)
J = rd(pr['attributes']['JOINTS_0']).astype(np.int64)
wac = G['accessors'][pr['attributes']['WEIGHTS_0']]
WMAX = 1.0 if wac['componentType'] == 5126 else float(np.iinfo(DT[wac['componentType']]).max)
W = rd(pr['attributes']['WEIGHTS_0']).astype(float) / WMAX

# 絵の色
mat = G['materials'][pr['material']]; ti = mat['pbrMetallicRoughness']['baseColorTexture']['index']
img = G['images'][G['textures'][ti]['source']]; bv = G['bufferViews'][img['bufferView']]
tmp = os.path.join(tempfile.gettempdir(), 'bagrig_tex' + ('.png' if img.get('mimeType', '').endswith('png') else '.jpg'))
open(tmp, 'wb').write(bytes(bd[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']]))
im = bpy.data.images.load(tmp); TW, TH = im.size
px = np.array(im.pixels[:], dtype=np.float32).reshape(TH, TW, 4)[:, :, :3]
cols = px[np.clip(((1 - UV[:, 1]) * TH).astype(int), 0, TH - 1), np.clip(((UV[:, 0] % 1) * TW).astype(int), 0, TW - 1)]

# 同じ位置の頂点をまとめる
key = np.round(P / 1e-5).astype(np.int64)
_, gid = np.unique(key, axis=0, return_inverse=True); gid = gid.ravel(); ng = gid.max() + 1
gcol = np.zeros((ng, 3)); np.add.at(gcol, gid, cols); gcol /= np.bincount(gid, minlength=ng)[:, None]
gpos = np.zeros((ng, 3)); gpos[gid] = P
hsv = np.array([colorsys.rgb_to_hsv(*c) for c in gcol])
h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
cls = np.full(ng, 2)                                   # 2 = 鞄・ベストなど
cls[(v >= 0.55) & (h >= 0.085) & (h <= 0.17)] = 1      # 1 = 短パン（ベージュ）
cls[(v >= 0.80) & ((h < 0.085) | (h > 0.95))] = 0      # 0 = 肌
cls[(v >= 0.80) & (s < 0.12)] = 0                     # 白い袖・シャツも触らない（袖が腕から外れて引き伸ばされた）
# 触らないのは腕の近くだけ。鞄の銀色の留め金も白と判定されて腕・脚の重みが残り、脚を上げると角がとがった
pa, pf, ph = JP[SIDE + 'Arm'], JP[SIDE + 'ForeArm'], JP[SIDE + 'Hand']
def segdist(Q, s0, s1):
    vv = s1 - s0; t = np.clip(((Q - s0) @ vv) / (vv @ vv), 0, 1)
    return np.linalg.norm(Q - (s0 + t[:, None] * vv), axis=1)
darm = np.min(np.stack([segdist(gpos, pa, pf), segdist(gpos, pf, ph), segdist(gpos, ph, ph + (ph - pf))]), 0)
skin0 = (v >= 0.80) & ((h < 0.085) | (h > 0.95)) & ~((v >= 0.80) & (s < 0.12))
white0 = (v >= 0.80) & (s < 0.12)
dup = segdist(gpos, pa, pf + (pf - pa) * 0.15)          # 上腕（肩〜肘の少し先）
# 肌は腕全体の骨から 5.5cm 以内、白（袖）は上腕から 9cm 以内だけ触らない。
# 一律 8cm だと手のそばの鞄の裏（白っぽい）に腕の重みが残り、一律 5.5cm だとゆったりした袖の裾が外れて引き伸ばされた
cls[(cls == 0) & ~((skin0 & (darm <= 0.055)) | (white0 & (dup <= 0.09)))] = 2
ea = np.concatenate([gid[T[:, 0]], gid[T[:, 1]], gid[T[:, 2]]]); eb = np.concatenate([gid[T[:, 1]], gid[T[:, 2]], gid[T[:, 0]]])
inbox = (gpos[:, 0] >= X0) & (gpos[:, 0] <= X1) & (gpos[:, 1] >= Y0) & (gpos[:, 1] <= Y1) & (gpos[:, 2] >= Z0) & (gpos[:, 2] <= Z1)
for it in range(2):                                    # 多数決でならす（自分も1票）
    votes = np.zeros((ng, 3)); votes[np.arange(ng), cls] += 1
    np.add.at(votes, (ea, cls[eb]), 1); np.add.at(votes, (eb, cls[ea]), 1)
    cls = np.where(inbox, votes.argmax(1), cls)
print("BR 箱の中 %d 位置：肌 %d・短パン %d・鞄など %d" % (int(inbox.sum()), int((inbox & (cls == 0)).sum()), int((inbox & (cls == 1)).sum()), int((inbox & (cls == 2)).sum())))

# 外す割合（腕・脚）。箱のふちで 0 へ
fa = np.where(inbox & (cls != 0), 1.0, 0.0); fl = np.where(inbox & (cls == 2), 1.0, 0.0)
nbc = np.bincount(ea, minlength=ng) + np.bincount(eb, minlength=ng)
for it in range(SMO):
    for arr in (fa, fl):
        sm = np.zeros(ng); np.add.at(sm, ea, arr[eb]); np.add.at(sm, eb, arr[ea])
        arr[:] = np.where(inbox, 0.5 * arr + 0.5 * sm / np.maximum(nbc, 1), 0.0)
fa[inbox & (cls == 0)] = 0.0                           # 肌は必ず触らない
wx = 0.15 * (X1 - X0); wy = 0.012; wz = 0.15 * (Z1 - Z0)   # 上下は 1.2cm だけ（15% だと鞄の上端が弱まり腕に残った）
edge = (np.clip(np.minimum(gpos[:, 0] - X0, X1 - gpos[:, 0]) / wx, 0, 1) * np.clip(np.minimum(gpos[:, 1] - Y0, Y1 - gpos[:, 1]) / wy, 0, 1)
        * np.clip(np.minimum(gpos[:, 2] - Z0, Z1 - gpos[:, 2]) / wz, 0, 1))
fa *= edge; fl *= edge
FA, FL = fa[gid], fl[gid]

moved_a = moved_l = 0.0
for vi in np.nonzero((FA > 0) | (FL > 0))[0]:
    acc = {}
    for k in range(J.shape[1]):
        if W[vi, k] > 0: acc[int(J[vi, k])] = acc.get(int(J[vi, k]), 0.0) + W[vi, k]
    moved = 0.0
    for ks, fr in ((ARMS, FA[vi]), (LEGS, FL[vi])):
        for k in ks:
            if k in acc and fr > 0:
                m = acc[k] * fr; acc[k] -= m; moved += m
                if ks is ARMS: moved_a += m
                else: moved_l += m
    if moved <= 0: continue
    th = {k: acc[k] for k in TRK if acc.get(k, 0) > 0}
    if th:
        st = sum(th.values())
        for k, w in th.items(): acc[k] += moved * w / st
    else:
        y = P[vi, 1]; o = np.argsort(np.abs(ty - y))[:2]
        dd = np.abs(ty[o] - y) + 1e-6; ww = (1 / dd) / (1 / dd).sum()
        for oi, w in zip(o, ww): acc[TRK[oi]] = acc.get(TRK[oi], 0.0) + moved * w
    top = sorted(acc.items(), key=lambda x: -x[1])[:J.shape[1]]
    st = sum(w for _, w in top) or 1.0
    J[vi] = 0; W[vi] = 0
    for k, (j, w) in enumerate(top): J[vi, k] = j; W[vi, k] = w / st
print("BR 外した重み：腕 %.1f・脚 %.1f（頂点の数で足した量）" % (moved_a, moved_l))

if WMAX == 1.0: Wout = W.astype(np.float32)
else:
    Wout = np.round(W * WMAX).astype(np.int64); Wout[:, 0] += int(WMAX) - Wout.sum(1)
wr(pr['attributes']['JOINTS_0'], J); wr(pr['attributes']['WEIGHTS_0'], Wout)
js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
bn = bytes(bd); bn += b'\x00' * ((4 - len(bn) % 4) % 4)
out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
open(DST, 'wb').write(out)
print("BR 書き出し", DST)
