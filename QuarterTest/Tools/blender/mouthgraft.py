# -*- coding: utf-8 -*-
"""別のモデルのテクスチャから、指定した球の中の「特徴のある色」だけを、こちらのテクスチャへ写す。
   貼り直しで口が閉じてしまったときに、前の版の口だけを持ってくるために使う。
   二つのモデルは頂点の位置がそろっている前提。位置で対応を取るので、UV が違っていても写せる。
   写すのは「元の色が指定した色の範囲に入っている画素」だけなので、肌の陰影は今の版のまま残る。
   実行: blender -b --factory-startup -P mouthgraft.py -- 元.glb 先.glb 出力テクスチャ.png x,y,z 半径"""
import bpy, sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import mathutils

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, OUT = a[0], a[1], a[2]
CEN = Vector(tuple(float(x) for x in a[3].split(',')))
RAD = float(a[4])

bpy.ops.wm.read_factory_settings(use_empty=True)

def load(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    added = [o for o in bpy.data.objects if o not in before]
    for o in list(added):
        if o.type == 'MESH' and o.name.startswith("Icosphere"):
            added.remove(o); bpy.data.objects.remove(o, do_unlink=True)
    me = next(o for o in added if o.type == 'MESH')
    img = None
    for m in me.data.materials:
        if not m or not m.use_nodes: continue
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
    return me, img

sme, simg = load(SRC)
dme, dimg = load(DST)
SW, SH = simg.size; DW, DH = dimg.size
S = np.array(simg.pixels[:], dtype=np.float32).reshape(SH, SW, 4)
D = np.array(dimg.pixels[:], dtype=np.float32).reshape(DH, DW, 4)
print("MG 元テクスチャ %dx%d  先テクスチャ %dx%d" % (SW, SH, DW, DH))

suv = sme.data.uv_layers.active.data
duv = dme.data.uv_layers.active.data
bvh = BVHTree.FromObject(sme, bpy.context.evaluated_depsgraph_get())
smw = sme.matrix_world; smwi = smw.inverted()

def is_mouth(c):
    r, g, b = float(c[0]), float(c[1]), float(c[2])
    # 口の中の暗い赤。髪の茶色（緑が赤の半分ほどある）と区別するため、
    # 「緑と青が赤の 0.35 倍より小さい」ことを条件にする。
    dark = (r > 0.25 and g < 0.35*r and b < 0.35*r)
    # 舌の桃色。ほおの赤み（緑が高い）と区別するため、上限を low くする。
    tong = (r > 0.80 and 0.33 < g < 0.62 and 0.33 < b < 0.62 and abs(g-b) < 0.10)
    return dark or tong

# 元の面ひとつが使っている画素の、平均の色を返す（一度計算したら覚えておく）。
# 元のテクスチャは面ごとに小さな断片が散らばって並んでいるため、
# 位置から求めた UV をそのまま使うと、わずかなずれで隣の断片（まったく別の場所）の色を拾ってしまう。
# 断片の中はほぼ一色なので、その面の画素の平均を使えばずれない。
_fc = {}
def face_color(idx):
    if idx in _fc: return _fc[idx]
    f = sme.data.polygons[idx]
    uv = [suv[li].uv for li in f.loop_indices]
    acc = np.zeros(3, np.float32); n = 0
    for i in range(1, len(uv)-1):
        tuv = [uv[0], uv[i], uv[i+1]]
        xs = [t.x*SW for t in tuv]; ys = [t.y*SH for t in tuv]
        x0 = max(0, int(min(xs))); x1 = min(SW-1, int(max(xs)))
        y0 = max(0, int(min(ys))); y1 = min(SH-1, int(max(ys)))
        den = (ys[1]-ys[2])*(xs[0]-xs[2]) + (xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(den) < 1e-12 or x1 < x0 or y1 < y0: continue
        for py in range(y0, y1+1):
            for px in range(x0, x1+1):
                gx, gy = px+0.5, py+0.5
                l1 = ((ys[1]-ys[2])*(gx-xs[2]) + (xs[2]-xs[1])*(gy-ys[2]))/den
                l2 = ((ys[2]-ys[0])*(gx-xs[2]) + (xs[0]-xs[2])*(gy-ys[2]))/den
                l3 = 1.0 - l1 - l2
                if l1 < 0.0 or l2 < 0.0 or l3 < 0.0: continue
                acc += S[py, px, :3]; n += 1
    if n == 0:
        u = uv[0]; px = int(u.x*SW) % SW; py = int(u.y*SH) % SH
        _fc[idx] = S[py, px, :3].copy()
    else:
        _fc[idx] = acc / n
    return _fc[idx]

written = 0; faces = 0
for f in dme.data.polygons:
    c = dme.matrix_world @ f.center
    if (c - CEN).length > RAD: continue
    faces += 1
    vs = [dme.data.vertices[v].co for v in f.vertices]
    uv = [duv[li].uv for li in f.loop_indices]
    for i in range(1, len(vs)-1):
        tri = [vs[0], vs[i], vs[i+1]]
        tuv = [uv[0], uv[i], uv[i+1]]
        # Blender の画素は下の行が先頭なので、v をそのまま行番号にする
        xs = [t.x*DW for t in tuv]; ys = [t.y*DH for t in tuv]
        x0 = max(0, int(min(xs))-1); x1 = min(DW-1, int(max(xs))+1)
        y0 = max(0, int(min(ys))-1); y1 = min(DH-1, int(max(ys))+1)
        if x1 < x0 or y1 < y0: continue
        den = (ys[1]-ys[2])*(xs[0]-xs[2]) + (xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(den) < 1e-12: continue
        for py in range(y0, y1+1):
            for px in range(x0, x1+1):
                gx, gy = px+0.5, py+0.5
                l1 = ((ys[1]-ys[2])*(gx-xs[2]) + (xs[2]-xs[1])*(gy-ys[2]))/den
                l2 = ((ys[2]-ys[0])*(gx-xs[2]) + (xs[0]-xs[2])*(gy-ys[2]))/den
                l3 = 1.0 - l1 - l2
                if l1 < -0.02 or l2 < -0.02 or l3 < -0.02: continue
                p = dme.matrix_world @ (tri[0]*l1 + tri[1]*l2 + tri[2]*l3)
                loc, nor, idx, dist = bvh.find_nearest(smwi @ p)
                if loc is None: continue
                col = face_color(idx)
                if col is None: continue
                if not is_mouth(col): continue
                D[py, px, :3] = col[:3]; written += 1
print("MG 球の中の面 %d 枚、写した画素 %d 個" % (faces, written))

out = bpy.data.images.new("grafted", DW, DH, alpha=True)
out.pixels = D.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save()
print("MG 書き出し", OUT)
