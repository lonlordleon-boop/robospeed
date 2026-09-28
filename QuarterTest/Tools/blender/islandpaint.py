# -*- coding: utf-8 -*-
"""指定の面が属する絵の島をまるごと髪の色で塗る。形・骨・重み・動きはそのまま、絵だけ。
   お嬢様（小学生編）は、目の横の房の内側（ほおの横、x±0.10〜0.12・高さ 0.93〜0.95m）に、肌色の絵が貼られた
   小さな房の切れ端（19 面・10 面・5 面…の島。まるごと肌色）があった。hairskinpaint.py は「半分以上が暗い島」の中だけ
   塗るので、島ぜんぶが肌色の房は対象に入らず、何度直しても残った（「髪の毛についた肌色…マスクできないのかな？」）。
   1) 指定の面が属する島（頂点のつながり）を集める
   2) 島の面の中の全画素を、島の近く（R 以内）の暗い面の色の中央値で塗る。面の中だけ塗る（すき間は hairpad.py で埋める）
   --mask で塗る所だけ緑のマスクの絵、--check で塗る所を緑にした確かめ用の glb を書く（--check のときは出力の絵を書かない）。
   **塗る前に必ず確かめ用の glb を前・横・下から描いて、耳や顔が入っていないことを見る**
   実行: blender -b --factory-startup -P islandpaint.py -- 入力.glb 出力.png f1,f2,.. [--r 0.03] [--mask マスク.png] [--check 確かめ.glb]"""
import bpy, sys, colorsys, collections, numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, default):
    global a
    if name in a: i = a.index(name); v = a[i+1]; a = a[:i] + a[i+2:]; return v
    return default
R = float(opt('--r', 0.03)); MASK = opt('--mask', None); CHECK = opt('--check', None)
SRC, OUT = a[0], a[1]; IDS = [int(x) for x in a[2].split(',')]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data; MW = me.matrix_world
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
par = list(range(len(m.vertices)))
def find(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
for e in m.edges:
    ra, rb = find(e.vertices[0]), find(e.vertices[1])
    if ra != rb: par[ra] = rb
def fcol(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0); return px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
comp = collections.defaultdict(list); dark = []
for p in m.polygons:
    comp[find(p.vertices[0])].append(p.index)
    if colorsys.rgb_to_hsv(*fcol(p))[2] < 0.4: dark.append(p.index)
kd = KDTree(len(dark))
for i, f in enumerate(dark): kd.insert(MW @ m.polygons[f].center, i)
kd.balance()
def raster(p):
    uv = [uvl[li].uv[:] for li in p.loop_indices]; out = []
    for k in range(1, len(uv) - 1):
        tri = np.array([uv[0], uv[k], uv[k+1]]) * [W_, H_]
        x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
        x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W_ - 1); y1 = min(y1, H_ - 1)
        if x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = tri; d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12: continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d; l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        M = (l1 >= -0.02) & (l2 >= -0.02) & (1 - l1 - l2 >= -0.02); out.append((y0, y1, x0, x1, M))
    return out
res = px.copy(); msk = np.zeros((H_, W_, 4), np.float32); msk[..., 3] = 1; done = set(); npx = 0
for fi in IDS:
    r = find(m.polygons[fi].vertices[0])
    if r in done: continue
    done.add(r); fs = comp[r]; c = sum((MW @ m.polygons[f].center for f in fs), Vector()) / len(fs)
    near = [dark[i] for _, i, _ in kd.find_range(c, R)]
    if not near: print("IP 島%d：近くに髪の面がない（R を広げる）" % r); continue
    hair = np.median(np.array([fcol(m.polygons[f]) for f in near]), 0); n = 0
    for f in fs:
        for y0, y1, x0, x1, M in raster(m.polygons[f]):
            sub = res[y0:y1+1, x0:x1+1]; sub[M, :3] = (0, 1, 0) if CHECK else hair
            ms = msk[y0:y1+1, x0:x1+1]; ms[M, :3] = (0, 1, 0); n += int(M.sum())
    npx += n; print("IP 島%d（%d 面・中心 %.3f,%.3f,%.3f）を髪の色 %s で塗った：%d 画素" % (r, len(fs), *c, tuple(round(float(x), 2) for x in hair), n))
print("IP 合計 %d 画素" % npx)
if MASK:
    im = bpy.data.images.new("m", W_, H_, alpha=True); im.pixels = msk.ravel(); im.filepath_raw = MASK; im.file_format = 'PNG'; im.save(); print("IP マスク", MASK)
if CHECK:
    img.scale(W_, H_); img.pixels = res.ravel(); img.pack()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=CHECK, export_format='GLB', export_animations=False, export_skins=True, export_yup=True); print("IP 確かめ用", CHECK)
else:
    im = bpy.data.images.new("o", W_, H_, alpha=True); im.pixels = res.ravel(); im.filepath_raw = OUT; im.file_format = 'PNG'; im.save(); print("IP 書き出し", OUT)
