# -*- coding: utf-8 -*-
"""髪の中に入り込んだ白い布の切れ端を、髪の色で塗り直す。形・骨・重み・動きはそのまま、絵だけ。
   お嬢様（小学生編）は、肩の上（高さ 0.80m・左右 0.12m）で、白いボレロの細長い面（長さ 3.5cm、左右 9〜10 面）が
   髪の中まで入り込んでいて、先が頭の重みで髪と一緒に動いた。歩くと服とずれて、髪の間から白いトゲが飛び出して見えた
   （「肩と髪がまだ引っ付いてる」）。形は元からある切れ端で、伸びではない。髪の中にあるので髪の色にする。
   1) 箱の中で、白い（明るさ ≥ 0.75・彩度 < 0.12）面のうち、頂点の頭の重みの最大が HMIN 以上のもの
   2) その面が覆う画素を、箱の中の髪の色（明るさ < 0.3 の画素の中央値）で塗る。明るさは元の比の 6 割で残す
      （ribbonfix.py・haircolorfix.py と同じ）。まわり 2 画素まで広げるが、ほかの面が覆う画素には広げない
   出力の PNG は swaptex.py で glb に差し替える
   実行: blender -b --factory-startup -P sliverpaint.py -- 入力.glb 元の絵.png 出力.png x0,x1,y0,y1,z0,z1 [x0,x1,...（箱をいくつでも）] [--hmin 0.5] [--vmin 0.75] [--wsrc 重みを拾うglb]
   お嬢様: --vmin 0.5 --wsrc ojou_e_ls3.glb（hairjoin.py の前）
   逆向き（袖に付いた髪の色を服の白へ）: [--tocloth 腕の重みの下限 0.8]"""
import bpy, sys, colorsys, numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
HMIN = 0.5; VMIN = 0.75; WSRC = None
if '--hmin' in a: i = a.index('--hmin'); HMIN = float(a[i+1]); a = a[:i] + a[i+2:]
# --vmin：白の明るさの下限。切れ端の陰の面は 0.67 前後で、0.75 では灰色のまま残った
if '--vmin' in a: i = a.index('--vmin'); VMIN = float(a[i+1]); a = a[:i] + a[i+2:]
# --wsrc：頭の重みを別の glb（同じ形）から、素の姿勢の位置で拾う。hairjoin.py でならした後は、
# 本物の肩の服にも頭の重みが混ざるので、ならす前のファイルで選ぶ
if '--wsrc' in a: i = a.index('--wsrc'); WSRC = a[i+1]; a = a[:i] + a[i+2:]
# --tocloth：逆向き。箱の中の暗い面（明るさ < 0.35）で、腕の重みが全頂点で AMIN 以上・頭の重みが 0 のものを、服の白で塗る。
# お嬢様は右袖の前の 3 面が髪の色で塗られていた（三面図で肩に乗った前髪の房の先が、生成で袖にくっついた）。
# 頭の重みで髪と動いていた間は袖との間が伸び、hairjoin.py で袖と動くようになると袖の上の黒い三角に見えた
TOCLOTH = '--tocloth' in a; AMIN = 0.8
if TOCLOTH: i = a.index('--tocloth'); AMIN = float(a[i+1]); a = a[:i] + a[i+2:]
SRC, TEX, OUT = a[0], a[1], a[2]
BOXES = [tuple(map(float, b.split(','))) for b in a[3:]]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data:
    for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
    arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = bpy.data.images.load(TEX)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data; MW = me.matrix_world
P = np.array([tuple(MW @ v.co) for v in m.vertices])
gi = {g.index: g.name for g in me.vertex_groups}
HW = np.zeros(len(m.vertices))
for v in m.vertices:
    for e in v.groups:
        if gi[e.group] == 'Head': HW[v.index] = e.weight
AW = np.array([sum(e.weight for e in v.groups if 'Arm' in gi[e.group] or 'Shoulder' in gi[e.group]) for v in m.vertices])
if WSRC:
    old = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=WSRC)
    m2o = next(o for o in bpy.data.objects if o not in old and o.type == 'MESH' and not o.name.startswith('Icosphere'))
    bpy.context.view_layer.update()   # 読み込んだ直後は置き方（倍率 0.01）がまだ計算されていない
    from mathutils import kdtree
    gi2 = {g.index: g.name for g in m2o.vertex_groups}; v2 = m2o.data.vertices
    kd = kdtree.KDTree(len(v2))
    for v in v2: kd.insert(m2o.matrix_world @ v.co, v.index)
    kd.balance(); miss = 0
    for i, p in enumerate(P):
        near = kd.find_range(p, 1e-4)   # 同じ位置の頂点（縫い目）はいちばん大きい頭の重み
        if near: HW[i] = max(sum(e.weight for e in v2[j].groups if gi2[e.group] == 'Head') for _, j, _ in near)
        else: miss += 1
    print("SP 頭の重みを %s から拾った（位置が合わない頂点 %d）" % (WSRC, miss))
def inbox(c): return any(B[0] <= c[0] <= B[1] and B[2] <= c[1] <= B[3] and B[4] <= c[2] <= B[5] for B in BOXES)
def fhsv(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    return colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])
sel = []; boxf = []
for p in m.polygons:
    vs = list(p.vertices)
    if not inbox(P[vs].mean(0)): continue
    h, s, v = fhsv(p)
    if TOCLOTH: ok = v < 0.35 and AW[vs].min() >= AMIN and HW[vs].max() < 0.01
    else: ok = v >= VMIN and s < 0.12 and HW[vs].max() >= HMIN
    if ok: sel.append(p.index)
    else: boxf.append(p.index)
print("SP 塗る面 %d（箱の中のほかの面 %d）" % (len(sel), len(boxf)))
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
MS = raster(sel, 0.02); MO = raster(boxf, 0.0)
tgt = MS.copy()
for _ in range(2):
    tgt = tgt | np.roll(tgt, 1, 0) | np.roll(tgt, -1, 0) | np.roll(tgt, 1, 1) | np.roll(tgt, -1, 1)
tgt &= ~(MO & ~MS)
rgb = px[:, :, :3]; L = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
ref_m = MO & (rgb.max(2) < 0.3)
if TOCLOTH: ref_m = MO & (rgb.max(2) > 0.75) & ((rgb.max(2) - rgb.min(2)) / np.maximum(rgb.max(2), 1e-6) < 0.12)   # 服の白
href = np.median(rgb[ref_m], 0); Lref = np.median(L[tgt])
h0, s0, v0 = colorsys.rgb_to_hsv(*href)
v = np.clip(v0 * (1 + 0.6 * (L[tgt] / Lref - 1)), 0, 1)
out = px.copy(); out[tgt, :3] = np.array([colorsys.hsv_to_rgb(h0, s0, x) for x in v])
print("SP 塗った色 %s  塗り直した画素 %d" % (np.round(href * 255).astype(int), int(tgt.sum())))
im = bpy.data.images.new("o", W_, H_, alpha=True); im.pixels = out.ravel(); im.filepath_raw = OUT; im.file_format = 'PNG'; im.save()
print("SP 書き出し", OUT)
