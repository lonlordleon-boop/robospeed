# -*- coding: utf-8 -*-
"""シーソーの男の子の、背中の白い星を消す（2026年9月23日）。

   三面図の背中には星が無いのに、Meshy が前の星を背中にも写した（前後で同じ絵を使いがち）。
   背中を向いた面（法線が後ろ = Blender の +Y 寄り）のうち、Tシャツの高さにある面だけを見て、
   白い画素（鮮やかさが低く明るい）を、同じ所の水色（Tシャツの色の中央値）で塗る。
   星の輪郭の線も消えるよう、白い画素のまわり 5 画素は色に関係なく塗る（陰影はまわりの明るさを内側へなじませる）。
   前の星は、前を向いた面なので触らない。

   実行: blender -b -P backstar.py -- 入力.glb 出力.glb 高さの下限,上限（お尻からの高さ。boyfit 後の座標） [左右の幅 0.2]
   例:   ... -- boy_fit.glb boy_fit_nostar.glb 0.05,0.80"""
import bpy, sys, os
import numpy as np
a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(a[0]), os.path.abspath(a[1])
Z0, Z1 = [float(v) for v in a[2].split(',')]
XMAX = float(a[3]) if len(a) > 3 else 0.2     # 背中の真ん中だけ（左右この幅まで）。広くすると腕の裏なども入り、塗る画素が絵じゅうに散らばった
def log(s): print("[backstar] " + str(s))

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=SRC)
me = next(o for o in bpy.context.scene.objects if o.type == 'MESH'); m = me.data
img = next(n.image for mt in m.materials if mt and mt.use_nodes for n in mt.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
A = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
MX = A[..., :3].max(-1); MN = A[..., :3].min(-1); S = np.where(MX > 0, (MX - MN) / np.maximum(MX, 1e-6), 0)
B = A[..., 2]; R = A[..., 0]
m.calc_loop_triangles(); uvl = m.uv_layers.active.data
MW = me.matrix_world
region = np.zeros((H, W), bool)
nf = 0
for t in m.loop_triangles:
    P = np.array([tuple(MW @ m.vertices[v].co) for v in t.vertices])
    n = np.cross(P[1] - P[0], P[2] - P[0]); ln = np.linalg.norm(n)
    if ln < 1e-12: continue
    n /= ln
    if n[1] < 0.35: continue                          # 背中（+Y）を向いた面だけ
    zc = P[:, 2].mean()
    if zc < Z0 or zc > Z1 or abs(P[:, 0].mean()) > XMAX: continue
    uv = np.array([tuple(uvl[l].uv) for l in t.loops]) * [W, H]
    x0, x1 = int(max(0, uv[:, 0].min() - 2)), int(min(W - 1, uv[:, 0].max() + 2))
    y0, y1 = int(max(0, uv[:, 1].min() - 2)), int(min(H - 1, uv[:, 1].max() + 2))
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    (ax, ay), (bx, by), (cx, cy) = uv; d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-9: continue
    l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d; l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d; l3 = 1 - l1 - l2
    ok = (l1 >= -0.05) & (l2 >= -0.05) & (l3 >= -0.05)
    region[y0:y1 + 1, x0:x1 + 1] |= ok; nf += 1
shirt = region & (S > 0.22) & (B > R)                  # 水色のTシャツ
white = region & (S < 0.16) & (MX > 0.62)             # 白い星
# 白い画素のまわり 5 画素は、色に関係なく塗る。星には細い輪郭の線（白ではなく少し暗い水色）があり、
# 白っぽい画素だけ塗ると、輪郭が線になって残った
near = white.copy()
for _ in range(5):
    g = near.copy(); g[1:] |= near[:-1]; g[:-1] |= near[1:]; g[:, 1:] |= near[:, :-1]; g[:, :-1] |= near[:, 1:]; near = g
paint = near & region
col = np.median(A[shirt, :3], axis=0)
log("背中の面 %d・Tシャツの画素 %d・白い画素 %d・塗る画素 %d・塗る色 %s" % (nf, shirt.sum(), white.sum(), paint.sum(), np.round(col, 3)))
# 陰影は、まわりの明るさを内側へなじませて埋める（塗る所だけ、上下左右の平均を何度も取る）。
# はじめは 25 画素四方の平均で合わせたが、星の真ん中はまわりに塗らない画素が無く、暗い星形のしみになった
vmed = np.median(MX[shirt & ~near])
V = MX.astype(np.float64).copy(); V[paint] = vmed
ys_, xs_ = np.nonzero(paint)
y0_, y1_, x0_, x1_ = max(0, ys_.min() - 2), min(H, ys_.max() + 3), max(0, xs_.min() - 2), min(W, xs_.max() + 3)
Vs = V[y0_:y1_, x0_:x1_]; Ps = paint[y0_:y1_, x0_:x1_]
for _ in range(400):
    nb = (np.roll(Vs, 1, 0) + np.roll(Vs, -1, 0) + np.roll(Vs, 1, 1) + np.roll(Vs, -1, 1)) / 4
    Vs[Ps] = nb[Ps]
k = np.clip(V[paint] / max(vmed, 1e-6), 0.75, 1.15)[:, None]
A[paint, :3] = col[None, :] * k
img.pixels.foreach_set(A.ravel())
png = os.path.splitext(OUT)[0] + '_tex.png'
img.filepath_raw = png; img.file_format = 'PNG'; img.save()
img.pack()   # ※ これをしても、下の書き出しには元の絵が出る。塗った絵（_tex.png）は swaptex.py で glb に差し替えること
bpy.ops.object.select_all(action='DESELECT'); me.select_set(True); bpy.context.view_layer.objects.active = me
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_yup=True,
                          export_animations=False, export_skins=False, export_image_format='JPEG', export_jpeg_quality=90)
log("書き出し: " + OUT)
