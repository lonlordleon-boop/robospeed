# -*- coding: utf-8 -*-
"""髪の中に入り込んだ白い布の切れ端の頂点を、すぐそばの肩の服と同じ重みにする。形・骨・動き・絵はそのまま、重みだけ。
   お嬢様（小学生編）は肩の上（高さ 0.80m・左右 0.12m）に、ボレロの細長い切れ端が髪の中まで入っていて、
   根元は肩、先は頭の重みだった。腕を下ろすと針のように突き出し、白いトゲになった。髪の色で塗ったら（sliverpaint.py）、
   止まっている時に肩の上の黒いかけらに見えた（「肩にまだ髪が付いてる」）。→ 色は白のまま、切れ端ごと肩の服と一緒に動かす。
   1) 箱の中で、白い（明るさ ≥ VMIN・彩度 < 0.12）面のうち、頭の重みの最大が 0.5 以上のもの＝切れ端
      頭の重みは REF（hairjoin.py の前のファイル。形は同じ）から素の姿勢の位置で拾う
   2) 切れ端の頂点の重みを、いちばん近い「箱の中の白い頂点で、REF の頭の重みが 0.05 未満」のものの重みにする
   実行: blender -b --factory-startup -P sliverweight.py -- 入力.glb REF.glb 出力.glb x0,x1,y0,y1,z0,z1 [箱をいくつでも] [--vmin 0.5] [--grow 2] [--paint 元の絵.png 出力.png]
   お嬢様: --grow 2 --paint ojou_e_v1_tex.png 出力.png（出力の絵は legpaint.py → swaptex.py へ）"""
import bpy, sys, colorsys, numpy as np
from mathutils import Matrix, kdtree
a = sys.argv[sys.argv.index("--")+1:]
VMIN = 0.5
if '--vmin' in a: i = a.index('--vmin'); VMIN = float(a[i+1]); a = a[:i] + a[i+2:]
# --grow N：切れ端の先についた小さな暗い面（辺がすべて 1.2cm 未満）も N 輪まで切れ端に入れる。
#   切れ端だけ肩と動かしたら、先の 3〜10mm の髪の面の片側だけが肩に引かれ、肩と髪の境目に 1cm ほどの黒い粒が出た
# --paint 元の絵.png 出力.png：入れた暗い面を服の白で塗る（肩と一緒に動くので服の一部にする）
GROW = 0; PAINT = None
if '--grow' in a: i = a.index('--grow'); GROW = int(a[i+1]); a = a[:i] + a[i+2:]
if '--paint' in a: i = a.index('--paint'); PAINT = (a[i+1], a[i+2]); a = a[:i] + a[i+3:]
SRC, REF, OUT = a[0], a[1], a[2]
BOXES = [tuple(map(float, b.split(','))) for b in a[3:]]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
bpy.context.view_layer.update()
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
P = np.array([tuple(me.matrix_world @ v.co) for v in m.vertices]); NV = len(P)
# REF の頭の重み（位置で拾う）
old = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=REF); bpy.context.view_layer.update()
ro = next(o for o in bpy.data.objects if o not in old and o.type == 'MESH' and not o.name.startswith('Icosphere'))
rgi = {g.index: g.name for g in ro.vertex_groups}; rv = ro.data.vertices
kd = kdtree.KDTree(len(rv))
for v in rv: kd.insert(ro.matrix_world @ v.co, v.index)
kd.balance()
HR = np.zeros(NV)
for i, p in enumerate(P):
    near = kd.find_range(p, 1e-4)
    if near: HR[i] = max(sum(e.weight for e in rv[j].groups if rgi[e.group] == 'Head') for _, j, _ in near)
for o in [o for o in bpy.data.objects if o not in old]: bpy.data.objects.remove(o, do_unlink=True)
def inbox(c): return any(B[0] <= c[0] <= B[1] and B[2] <= c[1] <= B[3] and B[4] <= c[2] <= B[5] for B in BOXES)
def fhsv(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    return colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])
S = set(); bright = set(); nf = 0
for p in m.polygons:
    vs = list(p.vertices)
    if not inbox(P[vs].mean(0)): continue
    h, s, v = fhsv(p)
    if v >= VMIN and s < 0.12:
        bright.update(vs)
        if HR[vs].max() >= 0.5: S.update(vs); nf += 1
# 同じ位置の頂点（縫い目）もまとめて
key = {}
for i in range(NV): key.setdefault(tuple(np.round(P[i], 5)), []).append(i)
S = {j for i in S for j in key[tuple(np.round(P[i], 5))]}
darkS = []
for _ in range(GROW):
    add = set()
    for p in m.polygons:
        vs = list(p.vertices)
        if p.index in darkS or not any(v in S for v in vs) or not inbox(P[vs].mean(0)): continue
        if fhsv(p)[2] >= 0.35: continue
        if max(np.linalg.norm(P[vs[k]] - P[vs[(k + 1) % len(vs)]]) for k in range(len(vs))) >= 0.012: continue
        darkS.append(p.index); add.update(vs)
    S |= {j for i in add for j in key[tuple(np.round(P[i], 5))]}
print("SW 先の小さな暗い面 %d を切れ端に入れた" % len(darkS))
base = [i for i in bright if i not in S and HR[i] < 0.05]
print("SW 切れ端の面 %d・頂点 %d  写し元の服の頂点 %d" % (nf, len(S), len(base)))
kb = kdtree.KDTree(len(base))
for n, i in enumerate(base): kb.insert(P[i], n)
kb.balance()
gi = {g.index: g.name for g in me.vertex_groups}
dmax = 0
for i in S:
    co, n, d = kb.find(P[i]); j = base[n]; dmax = max(dmax, d)
    src = [(e.group, e.weight) for e in m.vertices[j].groups]
    for e in list(m.vertices[i].groups): me.vertex_groups[e.group].remove([i])
    for g, w in src: me.vertex_groups[g].add([i], w, 'REPLACE')
print("SW 写し元までの距離の最大 %.3fm" % dmax)
if PAINT and darkS:
    im0 = bpy.data.images.load(PAINT[0]); TW, TH = im0.size
    tp = np.array(im0.pixels[:], np.float32).reshape(TH, TW, 4)
    def raster(faces, tol):
        M = np.zeros((TH, TW), bool)
        for fi in faces:
            p = m.polygons[fi]; uv = [uvl[li].uv[:] for li in p.loop_indices]
            for k in range(1, len(uv) - 1):
                tri = np.array([uv[0], uv[k], uv[k+1]]) * [TW, TH]
                x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
                x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, TW - 1); y1 = min(y1, TH - 1)
                if x1 < x0 or y1 < y0: continue
                xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                (ax, ay), (bx, by), (cx, cy) = tri
                d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
                if abs(d) < 1e-12: continue
                l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
                l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
                M[y0:y1 + 1, x0:x1 + 1] |= (l1 >= -tol) & (l2 >= -tol) & (1 - l1 - l2 >= -tol)
        return M
    ds = set(darkS)
    boxo = [p.index for p in m.polygons if p.index not in ds and inbox(P[list(p.vertices)].mean(0))]
    MS = raster(darkS, 0.02); MO = raster(boxo, 0.0)
    tgt = MS.copy()
    for _ in range(2):
        tgt = tgt | np.roll(tgt, 1, 0) | np.roll(tgt, -1, 0) | np.roll(tgt, 1, 1) | np.roll(tgt, -1, 1)
    tgt &= ~(MO & ~MS)
    rgb = tp[:, :, :3]; mx = rgb.max(2); mn = rgb.min(2)
    ref = MO & (mx > 0.75) & ((mx - mn) / np.maximum(mx, 1e-6) < 0.12)      # 箱の中の服の白
    col = np.median(rgb[ref], 0); out = tp.copy(); out[tgt, :3] = col
    im = bpy.data.images.new("o", TW, TH, alpha=True); im.pixels = out.ravel(); im.filepath_raw = PAINT[1]; im.file_format = 'PNG'; im.save()
    print("SW 服の白 %s で %d 画素を塗った → %s" % (np.round(col * 255).astype(int), int(tgt.sum()), PAINT[1]))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("SW 書き出し", OUT)
