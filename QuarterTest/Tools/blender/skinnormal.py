# -*- coding: utf-8 -*-
"""顔の肌の頂点だけ、面の向き（法線）をなめらかにする。形は動かさない。

   生成の顔は 1cm 以上の大きな三角形でできていて、光を当てると面の角ばりがでこぼこに見えた（わんぱく少女）。
   facesmooth.py の n（法線だけぼかす）は箱の中の前向きの点を全部ならすので、顔の前にある前髪の法線までならされ、
   髪の立体感が消える。ここでは絵の明るさで「肌」の頂点だけを選ぶ（facefit.py と同じ判定）。
   ・肌の頂点の法線を、正面から見た (x, 高さ) の平面でガウスの重みで平均する（肌の頂点どうしだけ）
   ・同じ位置の頂点（UV の継ぎ目で分かれたもの）は同じ向きにする。1つでも肌なら、その位置は肌として扱う
   ・箱のふち（幅の 20%）で元の向きへ段々に戻す
   鼻の形（nosebump.py）の正面の陰もやわらかくなる。横から見た鼻の形は変わらない。

   座標は glTF（X 左右・Y 上・Z 前）。
   実行: blender -b --factory-startup -P skinnormal.py -- 入力.glb 出力.glb x0,x1,y0,y1,z0 [σ 0.02] [明るさのしきい値 0.55]"""
import bpy, json, struct, sys, os, tempfile
import numpy as np
a = sys.argv[sys.argv.index("--") + 1:]
SRC, DST = a[0], a[1]
X0, X1, Y0, Y1, Z0 = [float(v) for v in a[2].split(',')]
SIG = float(a[3]) if len(a) > 3 else 0.02
LUM = float(a[4]) if len(a) > 4 else 0.55

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

cands = [(G['accessors'][m['primitives'][0]['attributes']['POSITION']]['count'], i)
         for i, m in enumerate(G['meshes']) if 'JOINTS_0' in m['primitives'][0]['attributes']]
pr = G['meshes'][max(cands)[1]]['primitives'][0]
P = rd(pr['attributes']['POSITION']).astype(float); N = rd(pr['attributes']['NORMAL']).astype(float)
UV = rd(pr['attributes']['TEXCOORD_0']).astype(float)

# 絵を読んで、頂点ごとの明るさ
mat = G['materials'][pr['material']]
ti = mat['pbrMetallicRoughness']['baseColorTexture']['index']
img = G['images'][G['textures'][ti]['source']]
bv = G['bufferViews'][img['bufferView']]; ib = bytes(bd[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']])
ext = '.png' if img.get('mimeType', '').endswith('png') else '.jpg'
tmp = os.path.join(tempfile.gettempdir(), 'skinnormal_tex' + ext); open(tmp, 'wb').write(ib)
im = bpy.data.images.load(tmp); W, H = im.size
A = np.array(im.pixels[:], dtype=np.float32).reshape(H, W, 4)
px = np.clip((UV[:, 0] % 1.0) * W, 0, W - 1).astype(int); py = np.clip((1.0 - (UV[:, 1] % 1.0)) * H, 0, H - 1).astype(int)
lum = A[py, px, :3].mean(1)
lum = np.where(lum <= 0.0031308, lum * 12.92, 1.055 * np.maximum(lum, 0) ** (1 / 2.4) - 0.055)

inbox = (P[:, 0] >= X0) & (P[:, 0] <= X1) & (P[:, 1] >= Y0) & (P[:, 1] <= Y1) & (P[:, 2] >= Z0)
skin = inbox & (lum > LUM) & (N[:, 2] > 0.15)
# 同じ位置の頂点をまとめる
key = np.round(P / 1e-5).astype(np.int64)
_, gid = np.unique(key, axis=0, return_inverse=True); gid = gid.ravel(); ng = gid.max() + 1
gskin = np.zeros(ng, bool); np.logical_or.at(gskin, gid, skin)
gpos = np.zeros((ng, 3)); gpos[gid] = P
gn = np.zeros((ng, 3)); np.add.at(gn, gid, N)
gn /= np.maximum(np.linalg.norm(gn, axis=1), 1e-12)[:, None]
sel = np.nonzero(gskin)[0]
print("SN 箱の中 %d 頂点、肌 %d（位置でまとめて %d）" % (int(inbox.sum()), int(skin.sum()), len(sel)))
XY = gpos[sel][:, :2]; NU = gn[sel]
R = 3 * SIG; NS = np.zeros_like(NU)
for k in range(len(sel)):
    d2 = ((XY - XY[k]) ** 2).sum(1); m = d2 < R * R
    w = np.exp(-0.5 * d2[m] / (SIG * SIG))
    v = (NU[m] * w[:, None]).sum(0); NS[k] = v / np.linalg.norm(v)
wx = 0.2 * (X1 - X0); wy = 0.2 * (Y1 - Y0)
f = np.clip(np.minimum(XY[:, 0] - X0, X1 - XY[:, 0]) / wx, 0, 1) * np.clip(np.minimum(XY[:, 1] - Y0, Y1 - XY[:, 1]) / wy, 0, 1)
f = (f * f * (3 - 2 * f))[:, None]
NF = NU * (1 - f) + NS * f; NF /= np.linalg.norm(NF, axis=1)[:, None]
ang = np.degrees(np.arccos(np.clip((NF * NU).sum(1), -1, 1)))
print("SN 法線の向きの変化 平均 %.1f度 最大 %.1f度" % (ang.mean(), ang.max()))
gnew = gn.copy(); gnew[sel] = NF
N2 = np.where(gskin[gid][:, None], gnew[gid], N)
wr(pr['attributes']['NORMAL'], N2.astype(np.float32))

js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
bn = bytes(bd); bn += b'\x00' * ((4 - len(bn) % 4) % 4)
out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
open(DST, 'wb').write(out)
print("SN 書き出し", DST)
