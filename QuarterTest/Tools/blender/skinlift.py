# -*- coding: utf-8 -*-
"""肌の影だけを薄くする（暗い画素ほど明るく、明るい画素はそのまま）。

   生成モデルは、あごの下や頬の外側に濃い影が焼き込まれていることがある。
   画面では小さく映るので、影が強いと「汚れ」や「くま」に見える。

   塗るのは **skinmask.py で作ったマスクの肌（赤）だけ**。髪や服は触らない。
   高さ z の範囲でさらに絞れる（顔の下半分だけ、など）。

   明るさに掛け算をするので、**色合いと鮮やかさは変わらない**（影が薄くなるだけ）。
   暗いほど強く、明るいほど弱く効く。

   実行: blender -b --factory-startup -P skinlift.py -- 入力.glb 出力.png mask=マスク.png z0,z1 量 [しきい値]
   例（ギャル少女の顔の下半分の影を薄く）: ... -- gy4.glb out.png mask=mask_gyaru.png 0.45,0.66 0.25
   量 0.25 = 真っ暗な所を最大25%明るくする。しきい値（既定 0.75）より明るい画素は触らない。
"""
import bpy, sys, os
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:]
MASKARG = next((v[5:] for v in a if v.startswith('mask=')), None)
a = [v for v in a if not v.startswith('mask=')]
SRC, OUT = a[0], a[1]
Z0, Z1 = [float(v) for v in a[2].split(',')]
AMT = float(a[3])
THR = float(a[4]) if len(a) > 4 else 0.75

def log(s):
    print("[skinlift] " + str(s))

def lin2srgb(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.maximum(c, 0) ** (1 / 2.4) - 0.055)
def srgb2lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
mesh = me.data
img = next(n.image for m in mesh.materials if m and m.use_nodes
           for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float64).reshape(H, W, 4)
C = np.clip(lin2srgb(A[:, :, :3]), 0, 1)

if not MASKARG:
    log("！ mask= が要る"); sys.exit(1)
mi = bpy.data.images.load(os.path.abspath(MASKARG))
if tuple(mi.size) != (W, H):
    log("！ マスクの大きさが絵と違う"); sys.exit(1)
MM = np.array(mi.pixels[:], dtype=np.float64).reshape(H, W, 4)[..., :3] > 0.5
SKIN = MM[..., 0] & ~MM[..., 1] & ~MM[..., 2]
log("マスクの肌 %d 画素（%.1f%%）" % (SKIN.sum(), 100 * SKIN.mean()))

# ---------------------------------------------------------------- 高さで絞る
P = np.array([tuple(v.co) for v in mesh.vertices])
S = P[:, 2].max() - P[:, 2].min(); bot = P[:, 2].min()
uvl = mesh.uv_layers.active.data
mesh.calc_loop_triangles()
REG = np.zeros((H, W), dtype=bool)
for t in mesh.loop_triangles:
    c = np.mean([P[i] for i in t.vertices], 0)
    z = (c[2] - bot) / S
    if not (Z0 <= z <= Z1): continue
    us = np.array([uvl[li].uv for li in t.loops], dtype=np.float64)
    xs = us[:, 0] * W; ys = us[:, 1] * H
    x0 = max(0, int(np.floor(xs.min())) - 1); x1 = min(W - 1, int(np.ceil(xs.max())) + 1)
    y0 = max(0, int(np.floor(ys.min())) - 1); y1 = min(H - 1, int(np.ceil(ys.max())) + 1)
    if x1 < x0 or y1 < y0: continue
    den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
    if abs(den) < 1e-12: continue
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    l1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
    l2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
    REG[y0:y1 + 1, x0:x1 + 1] |= (l1 >= -0.05) & (l2 >= -0.05) & (1 - l1 - l2 >= -0.05)
SEL = SKIN & REG
if SEL.sum() < 100:
    log("！ 塗る画素が無い（高さの範囲を見直すこと）"); sys.exit(1)

# ---------------------------------------------------------------- 影を薄くする
v = C.max(2)
w = np.clip((THR - v) / max(THR, 1e-6), 0, 1) * SEL
k = 1.0 + AMT * w
before = np.median(v[SEL])
NEW = np.clip(C * k[..., None], 0, 1)
after = np.median(NEW.max(2)[SEL])
log("塗った画素 %d  明るさの中央値 %.3f → %.3f  一番暗い所 %.3f → %.3f"
    % (SEL.sum(), before, after, v[SEL].min(), NEW.max(2)[SEL].min()))

A[:, :, :3] = srgb2lin(NEW)
img.pixels = A.ravel().tolist()
img.filepath_raw = os.path.abspath(OUT); img.file_format = 'PNG'; img.save()
log("書き出し: %s (%.2f MB)" % (OUT, os.path.getsize(OUT) / 1048576.0))
print("[skinlift] DONE")
