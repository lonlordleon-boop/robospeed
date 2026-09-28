# -*- coding: utf-8 -*-
"""モデルの指定した場所に当たるテクスチャの範囲を、まわりの色で塗りつぶす。
   生成時にテクスチャへ焼き付いてしまった小さな汚れを消すためのもの。
   面の中心が球の中に入っている面だけを対象にし、その面の UV を塗りつぶしの範囲にする。
   塗りつぶしは、範囲の外側の色を内側へ滲ませて埋める（周りの模様がそのまま続く）。
   実行: blender -b --factory-startup -P spotpatch.py -- 入力.glb 出力テクスチャ.png x,y,z:半径 [x,y,z:半径 ...]"""
import bpy, sys
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
SPOTS = []
for s in a[2:]:
    p, r = s.split(':')
    SPOTS.append((Vector(tuple(float(x) for x in p.split(','))), float(r)))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"):
        bpy.data.objects.remove(o, do_unlink=True)
me = next(o for o in bpy.data.objects if o.type == 'MESH')
mesh = me.data
uvl = mesh.uv_layers.active.data

img = None
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
if img is None:
    print("SP テクスチャが見つからない"); sys.exit(1)
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
print("SP テクスチャ %dx%d" % (W, H))

# glTF の座標のまま比べる（Blender は Z が上、glTF は Y が上）
def to_gltf(v):
    return Vector((v.x, v.z, -v.y))

mask = np.zeros((H, W), bool)
faces = 0
for f in mesh.polygons:
    c = to_gltf(me.matrix_world @ f.center)
    if not any((c - p).length < r for p, r in SPOTS): continue
    faces += 1
    uv = [uvl[li].uv for li in f.loop_indices]
    for i in range(1, len(uv)-1):
        tri = [uv[0], uv[i], uv[i+1]]
        # Blender の画素は下の行が先頭なので、v をそのまま行番号にする
        xs = [t.x*W for t in tri]; ys = [t.y*H for t in tri]
        x0 = max(0, int(min(xs))-1); x1 = min(W-1, int(max(xs))+1)
        y0 = max(0, int(min(ys))-1); y1 = min(H-1, int(max(ys))+1)
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1+1)+0.5, np.arange(y0, y1+1)+0.5)
        d = (ys[1]-ys[2])*(xs[0]-xs[2]) + (xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(d) < 1e-12: continue
        l1 = ((ys[1]-ys[2])*(gx-xs[2]) + (xs[2]-xs[1])*(gy-ys[2])) / d
        l2 = ((ys[2]-ys[0])*(gx-xs[2]) + (xs[0]-xs[2])*(gy-ys[2])) / d
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        mask[y0:y1+1, x0:x1+1] |= inside
print("SP 対象の面 %d 枚、塗りつぶす画素 %d 個" % (faces, int(mask.sum())))
if faces == 0:
    print("SP 何も当たらなかったので終わり"); sys.exit(0)

# ふちを少し広げる（面のすき間に汚れが残らないように）
for _ in range(2):
    m2 = mask.copy()
    m2[1:, :] |= mask[:-1, :]; m2[:-1, :] |= mask[1:, :]
    m2[:, 1:] |= mask[:, :-1]; m2[:, :-1] |= mask[:, 1:]
    mask = m2
print("SP 広げたあと %d 画素" % int(mask.sum()))

# 外側の色を内側へ滲ませて埋める
fill = A.copy()
todo = mask.copy()
for it in range(400):
    if not todo.any(): break
    valid = (~todo).astype(np.float32)
    acc = np.zeros_like(fill); cnt = np.zeros((H, W), np.float32)
    for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
        v = np.roll(valid, (dy,dx), (0,1)); c = np.roll(fill, (dy,dx), (0,1))
        acc += c*v[:,:,None]; cnt += v
    can = todo & (cnt > 0)
    if not can.any(): break
    fill[can] = (acc[can] / cnt[can][:,None])
    todo &= ~can
print("SP 埋め終わり 残り %d 画素" % int(todo.sum()))

out = bpy.data.images.new("patched", W, H, alpha=True)
out.pixels = fill.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save()
print("SP 書き出し", OUT)
