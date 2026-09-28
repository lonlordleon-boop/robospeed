# -*- coding: utf-8 -*-
"""顔の「ヒビ」を消す：肌の面の向き（法線）だけを直す。形（彫った目・口・鼻）は動かさない（2026年9月23日、乳児期の赤ちゃん）。

   ヒビは絵ではなく法線のせいだった（光を切って描くとヒビが無い）。
   ・生成のメッシュは絵の継ぎ目で頂点が切れていて、切れた頂点どうしで法線が違う → 継ぎ目が線になって見えた
   ・三角形ごとに法線の向きがそろっておらず、光を当てると継ぎはぎのまだらに見えた
   やること:
   1. 同じ位置の頂点をまとめ、面の向きから法線を計算し直す（切れた頂点も同じ向きになる）
   2. 隣どうしで、向きの差が ANG 度より小さいものだけを平均する（何回か）。彫りの縁（急な角度）はまたがないので、彫りは残る
   3. 箱のふちで元の向きへ段々に戻す
   選ぶのは箱の中の肌・目・口の頂点（前髪とフードは色で外す）。
   以前の babyface.py（形を平らにした）は没。skinnormal.py は正面の平面で平均するので、あごの下の向きが混ざり黒いしみが出た。

   glb を直接書き換えるので、骨・動き・絵は変わらない。座標は glTF（X 左右・Y 上・Z 前）。
   実行: blender -b --factory-startup -P facenormal.py -- 入力.glb 出力.glb [ANG 40] [回数 12]"""
import bpy, json, struct, sys, os, tempfile
import numpy as np
a = sys.argv[sys.argv.index("--") + 1:]
SRC, DST = a[0], a[1]
ANG = float(a[2]) if len(a) > 2 else 40.0
ITER = int(a[3]) if len(a) > 3 else 12
# 顔の箱（glTF 座標。左右・高さ・前の下限）。あごの下まで入れる
BOX = (-0.40, 0.40, 0.66, 1.30, 0.40)
FALL = 0.05

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0] + Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO + BL])
DT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NUM = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
def view(i):
    ac = G['accessors'][i]; bv = G['bufferViews'][ac['bufferView']]
    n = NUM[ac['type']]; dt = np.dtype(DT[ac['componentType']])
    b = bv.get('byteOffset', 0) + ac.get('byteOffset', 0); st = bv.get('byteStride') or n * dt.itemsize
    return ac, n, dt, b, st
def rd(i):
    ac, n, dt, b, st = view(i)
    out = np.empty((ac['count'], n), dt)
    for k in range(n): out[:, k] = np.ndarray((ac['count'],), dt, bd, b + k * dt.itemsize, (st,))
    return out
def wr(i, arr):
    ac, n, dt, b, st = view(i)
    for k in range(n):
        v = np.ndarray((ac['count'],), dt, bd, b + k * dt.itemsize, (st,)); v[:] = arr[:, k]

cands = [(G['accessors'][m['primitives'][0]['attributes']['POSITION']]['count'], i) for i, m in enumerate(G['meshes'])]
pr = G['meshes'][max(cands)[1]]['primitives'][0]
P = rd(pr['attributes']['POSITION']).astype(float); N = rd(pr['attributes']['NORMAL']).astype(float)
UV = rd(pr['attributes']['TEXCOORD_0']).astype(float)
tri = rd(pr['indices']).astype(np.int64).reshape(-1, 3)

# 絵の色（頂点ごと）
mat = G['materials'][pr['material']]
ti = mat['pbrMetallicRoughness']['baseColorTexture']['index']
img = G['images'][G['textures'][ti]['source']]
bv = G['bufferViews'][img['bufferView']]; ib = bytes(bd[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']])
ext = '.png' if img.get('mimeType', '').endswith('png') else '.jpg'
tmp = os.path.join(tempfile.gettempdir(), 'facenormal_tex' + ext); open(tmp, 'wb').write(ib)
im = bpy.data.images.load(tmp); W, H = im.size
A = np.array(im.pixels[:], dtype=np.float32).reshape(H, W, 4)
px = np.clip((UV[:, 0] % 1.0) * W, 0, W - 1).astype(int); py = np.clip((1.0 - (UV[:, 1] % 1.0)) * H, 0, H - 1).astype(int)
C = A[py, px, :3]; MX = C.max(1); MN = C.min(1); S = (MX - MN) / np.maximum(MX, 1e-6)

X0, X1, Y0, Y1, ZF = BOX
inbox = (P[:, 0] > X0) & (P[:, 0] < X1) & (P[:, 1] > Y0) & (P[:, 1] < Y1) & (P[:, 2] > ZF)
# 目と口は暗い色もあるので、位置で入れる（Blender で測った目 z 0.90〜1.12・|x| 0.06〜0.34、口 |x|<0.13・z 0.81〜0.94）
eye = (np.abs(P[:, 0]) > 0.06) & (np.abs(P[:, 0]) < 0.34) & (P[:, 1] > 0.90) & (P[:, 1] < 1.12)
mouth = (np.abs(P[:, 0]) < 0.13) & (P[:, 1] > 0.81) & (P[:, 1] < 0.94)
bright = MX > 0.55                                    # 肌（前髪とフードは暗い）
sel = inbox & (bright | eye | mouth)

# 同じ位置の頂点をまとめる
key = np.round(P / 1e-5).astype(np.int64)
_, gid = np.unique(key, axis=0, return_inverse=True); gid = gid.ravel(); ng = gid.max() + 1
gsel = np.zeros(ng, bool); np.logical_or.at(gsel, gid, sel)
gpos = np.zeros((ng, 3)); gpos[gid] = P
# 面の向きから法線（面積の重み）
gt = gid[tri]
fn = np.cross(gpos[gt[:, 1]] - gpos[gt[:, 0]], gpos[gt[:, 2]] - gpos[gt[:, 0]])
gn = np.zeros((ng, 3))
for k in range(3): np.add.at(gn, gt[:, k], fn)
gn /= np.maximum(np.linalg.norm(gn, axis=1), 1e-12)[:, None]
g0 = np.zeros((ng, 3)); np.add.at(g0, gid, N); g0 /= np.maximum(np.linalg.norm(g0, axis=1), 1e-12)[:, None]
# となりどうし（辺）
e = np.concatenate([gt[:, [0, 1]], gt[:, [1, 2]], gt[:, [2, 0]]])
e = e[(gsel[e[:, 0]]) | (gsel[e[:, 1]])]
e = np.unique(np.sort(e, 1), axis=0)
cth = np.cos(np.radians(ANG))
n = gn.copy(); n_early = None
for it in range(ITER):
    ok = (n[e[:, 0]] * n[e[:, 1]]).sum(1) > cth
    acc = n.copy()
    np.add.at(acc, e[ok, 0], n[e[ok, 1]]); np.add.at(acc, e[ok, 1], n[e[ok, 0]])
    acc /= np.maximum(np.linalg.norm(acc, axis=1), 1e-12)[:, None]
    n = np.where(gsel[:, None], acc, n)
    if it == 1: n_early = n.copy()
# 鼻は小さな盛り上がりなので、何回もならすと陰が消えた。鼻先（顔の真ん中で一番前の点）のまわりは 2 回だけにする
cm = gsel & (np.abs(gpos[:, 0]) < 0.05) & (gpos[:, 1] > 0.84) & (gpos[:, 1] < 1.02)
tip = gpos[np.nonzero(cm)[0][np.argmax(gpos[cm, 2])]]
dn = np.linalg.norm(gpos - tip, axis=1)
kn = np.clip((dn - 0.035) / 0.025, 0, 1)
# 目の彫りも浅いので、何回もならすと形だけの絵で目が消えた。目の中も 2 回だけにする（ふちはなめらかに切り替える）
ex = np.abs(gpos[:, 0]); ey = gpos[:, 1]
ke = 1 - (np.clip((ex - 0.08) / 0.02, 0, 1) * np.clip((0.32 - ex) / 0.02, 0, 1) * np.clip((ey - 0.92) / 0.02, 0, 1) * np.clip((1.10 - ey) / 0.02, 0, 1))
kn = np.minimum(kn, ke)[:, None]                        # 鼻・目 0 … まわり 1
# 鼻はならさない（面の向きから計算し直すだけ）。2 回ならしても盛り上がりの陰が弱まり「鼻の色が消えた」と言われた。
# 絵の鼻の点は薄く、陰と合わさって初めて鼻に見える
kn_nose = np.clip((dn - 0.035) / 0.025, 0, 1)[:, None]
base = np.where(kn_nose < 1, gn, n_early)
base = gn * (1 - kn_nose) + n_early * kn_nose; base /= np.maximum(np.linalg.norm(base, axis=1), 1e-12)[:, None]
n = base * (1 - kn) + n * kn; n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
print("FN 鼻先 %s" % np.round(tip, 3))
# 箱のふちで元の向きへ戻す
def ramp(v, lo, hi):
    t = np.clip(np.minimum(v - lo, hi - v) / FALL, 0, 1); return t * t * (3 - 2 * t)
f = (ramp(gpos[:, 0], X0, X1) * ramp(gpos[:, 1], Y0, Y1) * np.clip((gpos[:, 2] - ZF) / FALL, 0, 1))[:, None]
nf = g0 * (1 - f) + n * f; nf /= np.maximum(np.linalg.norm(nf, axis=1), 1e-12)[:, None]
N2 = np.where(gsel[gid][:, None], nf[gid], N)
ang = np.degrees(np.arccos(np.clip((N2 * N).sum(1), -1, 1)))[sel[:]]
print("FN 選んだ頂点 %d（位置でまとめて %d）・向きの変化 平均 %.1f度 最大 %.1f度" % (sel.sum(), gsel.sum(), ang.mean(), ang.max()))
wr(pr['attributes']['NORMAL'], N2.astype(np.float32))

js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
bn = bytes(bd); bn += b'\x00' * ((4 - len(bn) % 4) % 4)
out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
open(DST, 'wb').write(out)
print("FN 書き出し", DST)
