# -*- coding: utf-8 -*-
"""脚の肌に入った白（靴下・スカートの色）を肌色で塗り直す。形・骨・重み・動きはそのまま、絵だけ。
   お嬢様（小学生編）は、ひざ下の内側（すねの裏、高さ 0.18〜0.28m）と、スカートの中の太もも（0.36〜0.48m）の面が
   白く塗られていて、歩き・スキップで脚の白い線（「太ももの裏地の筋」）に見えた。面は脚の骨の重み 1.0 で、伸びではない。
   1) 面の中心が高さ Z0〜Z1、脚の骨（もも・すね）から RL 以内、脚の骨の重みが全頂点で 0.9 以上、白い（彩度 < 0.10・明るさ > 0.7）
   2) その面が覆う画素を、同じ範囲の肌の面の色（中央値）で塗る。明るさは元の比の 6 割で残す（ほかの塗り直しと同じ）。
      まわり 2 画素まで広げるが、ほかの面が覆う画素には広げない
   Z0 は靴下の上のふちのすぐ上（お嬢様 0.17m。靴下は 0.16m まで）
   出力の PNG は swaptex.py で glb に差し替える
   実行: blender -b --factory-startup -P legpaint.py -- 入力.glb 元の絵.png 出力.png [Z0 0.17] [Z1 0.48] [RL 0.07]"""
import bpy, sys, colorsys, numpy as np
from mathutils import Matrix, Vector
from mathutils.geometry import intersect_point_line
a = sys.argv[sys.argv.index("--")+1:]; SRC, TEX, OUT = a[0], a[1], a[2]
Z0 = float(a[3]) if len(a) > 3 else 0.17
Z1 = float(a[4]) if len(a) > 4 else 0.48
RL = float(a[5]) if len(a) > 5 else 0.07
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data:
    for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
    arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = bpy.data.images.load(TEX)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data; MW = me.matrix_world
P = np.array([tuple(MW @ v.co) for v in m.vertices])
gi = {g.index: g.name for g in me.vertex_groups}
LW = np.array([sum(e.weight for e in v.groups if gi[e.group].endswith(('UpLeg', 'Leg'))) for v in m.vertices])
def bh(n): return arm.matrix_world @ arm.data.bones[n].head_local
LSEG = [(bh(s + 'UpLeg'), bh(s + 'Leg')) for s in ('Left', 'Right')] + [(bh(s + 'Leg'), bh(s + 'Foot')) for s in ('Left', 'Right')]
def legdist(p):
    pv = Vector(p); best = 9.0
    for h, t in LSEG:
        q, f = intersect_point_line(pv, h, t); f = min(1.0, max(0.0, f)); best = min(best, (pv - (h + (t - h) * f)).length)
    return best
def fhsv(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    return colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])
sel = []; skin = []; other = []
for p in m.polygons:
    vs = list(p.vertices); c = P[vs].mean(0)
    if not (Z0 <= c[2] <= Z1) or legdist(c) > RL or LW[vs].min() < 0.9: continue
    h, s, v = fhsv(p)
    # 肌はとても薄い（彩度 0.12〜0.15）。0.15 未満を白にしたら肌の面まで選んだ。靴下は 0、白い筋は 0〜0.04、太ももの白は 0〜0.10
    if s < 0.10 and v > 0.7: sel.append(p.index)
    else:
        other.append(p.index)
        if 0.02 < h < 0.11 and s >= 0.12 and v > 0.5: skin.append(p.index)
print("LP 塗る面 %d  肌の面 %d" % (len(sel), len(skin)))
def raster(faces, tol):
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
            M[y0:y1 + 1, x0:x1 + 1] |= (l1 >= -tol) & (l2 >= -tol) & (1 - l1 - l2 >= -tol)
    return M
MS = raster(sel, 0.02); MK = raster(skin, 0.0)
# ほかの面（脚の外の面も含む）が覆う画素には広げない
MO = raster([p.index for p in m.polygons if p.index not in set(sel)], 0.0)
tgt = MS.copy()
for _ in range(2):
    tgt = tgt | np.roll(tgt, 1, 0) | np.roll(tgt, -1, 0) | np.roll(tgt, 1, 1) | np.roll(tgt, -1, 1)
tgt &= ~(MO & ~MS)
rgb = px[:, :, :3]; L = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
href = np.median(rgb[MK & ~MS], 0); Lref = np.median(L[tgt])
h0, s0, v0 = colorsys.rgb_to_hsv(*href)
v = np.clip(v0 * (1 + 0.6 * (L[tgt] / Lref - 1)), 0, 1)
out = px.copy(); out[tgt, :3] = np.array([colorsys.hsv_to_rgb(h0, s0, x) for x in v])
print("LP 肌の色 %s  塗り直した画素 %d" % (np.round(href * 255).astype(int), int(tgt.sum())))
im = bpy.data.images.new("o", W_, H_, alpha=True); im.pixels = out.ravel(); im.filepath_raw = OUT; im.file_format = 'PNG'; im.save()
print("LP 書き出し", OUT)
