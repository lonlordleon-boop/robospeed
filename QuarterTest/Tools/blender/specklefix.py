# -*- coding: utf-8 -*-
"""テクスチャの「ひとりぼっちの色違いの面」を、まわりの色で塗り直す。

   Meshy の貼り直しが吐くテクスチャは三角形ごとにバラバラの断片として並んでいるので、
   色の境目（下着の裾のような線）が面ごとにギザギザになる。
   素体だけを見ても裾がのこぎり状に見えるし、上から服を着せると、その白いギザギザだけが
   服の縁から顔を出して「股に穴が開いている」ように見えた。形ではなく絵の問題なので、
   メッシュをならしても直らない。

   直し方は、面ごとに2つ隣までの色の中央値を取り、自分の色がそこから大きく外れていて、
   しかも自分と近い色の隣がほとんど無い面だけを塗り替える。
   境目そのものは隣の半分が同じ色なので残り、飛び出した数枚だけが消える。

   実行: blender -b --factory-startup -P specklefix.py -- 入力.glb 元テクスチャ 出力テクスチャ
         [色の差のしきい値 既定0.18] [同じ色の隣の割合の上限 既定0.30] [高さ z下,z上 既定すべて] [mark]
   mark を付けると、直した場所を緑に塗って確認できる。
   そのあと swaptex.py で GLB に戻す。
"""
import bpy, sys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, TEX, OUT = a[0], a[1], a[2]
THR = float(a[3]) if len(a) > 3 else 0.18
RATIO = float(a[4]) if len(a) > 4 else 0.30
ZR = [float(v) for v in a[5].split(',')] if len(a) > 5 and a[5] and ',' in a[5] else None
MARK = a[-1] == 'mark'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
ob = next(o for o in bpy.data.objects if o.type == 'MESH'); me = ob.data
img = bpy.data.images.load(TEX); W, H = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
uvl = me.uv_layers.active.data
NF = len(me.polygons)
print("SP テクスチャ %dx%d  面 %d" % (W, H, NF))

col = np.zeros((NF, 3)); ctr = np.zeros((NF, 3))
for f in me.polygons:
    uv = np.array([uvl[li].uv for li in f.loop_indices])
    cs = [px[int(np.clip(u[1], 0, .9999)*H), int(np.clip(u[0], 0, .9999)*W), :3] for u in uv]
    col[f.index] = np.mean(cs, 0)
    ctr[f.index] = np.mean([tuple(ob.matrix_world @ me.vertices[me.loops[li].vertex_index].co)
                            for li in f.loop_indices], 0)

e2f = {}
for f in me.polygons:
    for e in f.edge_keys: e2f.setdefault(e, []).append(f.index)
nb = [[] for _ in range(NF)]
for f in me.polygons:
    for e in f.edge_keys: nb[f.index] += [j for j in e2f.get(e, []) if j != f.index]
nb2 = [list(set(sum([nb[j] for j in nb[i]], []) + nb[i]) - {i}) for i in range(NF)]

bad = {}
for i in range(NF):
    ns = nb2[i]
    if len(ns) < 4: continue
    if ZR is not None and not (ZR[0] <= ctr[i][2] <= ZR[1]): continue
    m = np.median(col[ns], axis=0)
    if np.linalg.norm(col[i] - m) <= THR: continue
    same = sum(1 for j in ns if np.linalg.norm(col[j] - col[i]) <= THR)
    if same / len(ns) > RATIO: continue          # 境目はここで残る
    bad[i] = m
print("SP まわりから浮いている面 %d 枚を塗り直す" % len(bad))
if not bad:
    print("SP 直すところが無い"); sys.exit(0)

me.calc_loop_triangles()
tri_of = [[] for _ in range(NF)]
for t in me.loop_triangles: tri_of[t.polygon_index].append(t)
n = 0
for i, c in bad.items():
    for t in tri_of[i]:
        uv = np.array([uvl[li].uv for li in t.loops], float)
        xs = uv[:,0]*W; ys = uv[:,1]*H
        x0 = max(0, int(np.floor(xs.min()))-1); x1 = min(W-1, int(np.ceil(xs.max()))+1)
        y0 = max(0, int(np.floor(ys.min()))-1); y1 = min(H-1, int(np.ceil(ys.max()))+1)
        if x1 < x0 or y1 < y0 or (x1-x0) > 300 or (y1-y0) > 300: continue
        gx, gy = np.meshgrid(np.arange(x0, x1+1)+0.5, np.arange(y0, y1+1)+0.5)
        d = (ys[1]-ys[2])*(xs[0]-xs[2]) + (xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(d) < 1e-12: continue
        l1 = ((ys[1]-ys[2])*(gx-xs[2]) + (xs[2]-xs[1])*(gy-ys[2]))/d
        l2 = ((ys[2]-ys[0])*(gx-xs[2]) + (xs[0]-xs[2])*(gy-ys[2]))/d
        l3 = 1.0 - l1 - l2
        m = (l1 > -0.08) & (l2 > -0.08) & (l3 > -0.08)
        if not m.any(): continue
        yy = gy[m].astype(int); xx = gx[m].astype(int)
        px[yy, xx, :3] = (0.0, 1.0, 0.0) if MARK else c
        n += int(m.sum())
print("SP 塗った画素 %d 個" % n)

out = bpy.data.images.new("fixed", W, H, alpha=True)
out.pixels = px.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save()
print("SP 書き出し", OUT)
