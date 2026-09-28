# -*- coding: utf-8 -*-
"""箱の中の髪に入った別の色（貼り直しの塗り間違い）を、まわりの髪の色で塗り直す。形・骨・動きはそのまま。
   お嬢様（小学生編）は貼り直しで、左の耳の前の髪にリボンの紺が1筋入った（93面）。
   1) 箱の中で、色が「色相 H0〜H1・彩度 SMIN 以上」の面を選ぶ
   2) その面が覆う画素のうち、その色の画素を、箱の中の髪の色（明るさ < DARK の画素の中央値）で塗る。
      色合い・鮮やかさは髪に固定し、明るさだけ元の比の 6 割で残す（ribbonfix.py と同じ）
   出力の PNG は swaptex.py で glb に差し替える
   実行: blender -b --factory-startup -P haircolorfix.py -- 入力.glb 出力.png x0,x1,y0,y1,z0,z1 [H0 195] [H1 265] [SMIN 0.2] [DARK 0.3]"""
import bpy, sys, colorsys, numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
BOX = tuple(map(float, a[2].split(',')))
H0 = float(a[3]) if len(a) > 3 else 195.0; H1 = float(a[4]) if len(a) > 4 else 265.0
SMIN = float(a[5]) if len(a) > 5 else 0.2; DARK = float(a[6]) if len(a) > 6 else 0.3
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data:
    for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
    arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data; MW = me.matrix_world
P = np.array([tuple(MW @ v.co) for v in m.vertices])
def inbox(c): return BOX[0] <= c[0] <= BOX[1] and BOX[2] <= c[1] <= BOX[3] and BOX[4] <= c[2] <= BOX[5]
def fhsv(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    return colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])
sel = []; boxf = []
for p in m.polygons:
    c = P[list(p.vertices)].mean(0)
    if not inbox(c): continue
    boxf.append(p.index)
    h, s, v = fhsv(p)
    if H0/360 <= h <= H1/360 and s >= SMIN: sel.append(p.index)
print("HC 箱の中の面 %d  直す色の面 %d" % (len(boxf), len(sel)))
def raster(faces):
    M = np.zeros((H_, W_), bool)
    for fi in faces:
        p = m.polygons[fi]; uv = [uvl[li].uv[:] for li in p.loop_indices]
        for k in range(1, len(uv) - 1):
            tri = np.array([uv[0], uv[k], uv[k+1]]) * [W_, H_]
            x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
            x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W_ - 1); y1 = min(y1, H_ - 1)
            if x1 < x0 or y1 < y0: continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = tri
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-12: continue
            l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
            l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
            M[y0:y1 + 1, x0:x1 + 1] |= (l1 >= -0.02) & (l2 >= -0.02) & (1 - l1 - l2 >= -0.02)
    return M
MS = raster(sel); MB = raster(boxf)
rgb = px[:, :, :3]; mx = rgb.max(2); mn = rgb.min(2); d = np.maximum(mx - mn, 1e-6)
r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
L = 0.299 * r + 0.587 * g + 0.114 * b
# 面を選ばず、箱の中の面が覆う画素すべてから直す色を探す（紺の面だけでは、黒と判定された面の中の筋が残った）
# 絵の切れ目のすき間（どの面も覆わない帯）の紺も、描く時ににじむので、まわり4画素まで広げて探す
MBd = MB.copy()
for _ in range(4):
    MBd = MBd | np.roll(MBd, 1, 0) | np.roll(MBd, -1, 0) | np.roll(MBd, 1, 1) | np.roll(MBd, -1, 1)
tgt = MBd & (hue >= H0) & (hue <= H1) & (sat >= SMIN)
ref_m = MB & ~tgt & (mx < DARK)
href = np.median(rgb[ref_m], 0); Lref = np.median(L[tgt]) if tgt.any() else 1
h0, s0, v0 = colorsys.rgb_to_hsv(*href)
v = np.clip(v0 * (1 + 0.6 * (L[tgt] / Lref - 1)), 0, 1)
out = px.copy(); out[tgt, :3] = np.array([colorsys.hsv_to_rgb(h0, s0, x) for x in v])
print("HC 髪の色 %s  塗り直した画素 %d" % (np.round(href * 255).astype(int), int(tgt.sum())))
im = bpy.data.images.new("o", W_, H_, alpha=True); im.pixels = out.ravel(); im.filepath_raw = OUT; im.file_format = 'PNG'; im.save()
print("HC 書き出し", OUT)
