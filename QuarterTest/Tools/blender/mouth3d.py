# -*- coding: utf-8 -*-
"""別のモデルのテクスチャから、口の絵を「3次元の位置」で写す。
   二つのテクスチャは並べ方がまったく違うので、UV では対応が取れない。
   そこで、元のテクスチャの画素ひとつずつについて「モデルのどこに当たるか」を求めておき、
   写す先の画素も同じように位置を求めて、一番近い元の画素の色を持ってくる。
   口の色をしている画素だけを対象にするので、まわりの肌はそのまま残る。
   実行: blender -b --factory-startup -P mouth3d.py -- 元.glb 先.glb 出力テクスチャ.png 箱xlo,xhi,ylo,yhi,zlo,zhi 近さ"""
import bpy, sys
import numpy as np
from mathutils import kdtree

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, OUT = a[0], a[1], a[2]
BOX = [float(x) for x in a[3].split(',')]
EPS = float(a[4])
xlo, xhi, ylo, yhi, zlo, zhi = BOX

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
    W, H = img.size
    A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    return me, img, A, W, H

def scan(me, A, W, H):
    """箱の中に当たる画素を、位置と色の組で返す"""
    mesh = me.data; uvl = mesh.uv_layers.active.data; MW = me.matrix_world
    out = []
    for f in mesh.polygons:
        c = MW @ f.center
        if c.x < xlo-0.05 or c.x > xhi+0.05: continue
        if c.y < ylo-0.05 or c.y > yhi+0.05: continue
        if c.z < zlo-0.05 or c.z > zhi+0.05: continue
        vs = [mesh.vertices[v].co for v in f.vertices]
        uv = [uvl[li].uv for li in f.loop_indices]
        for i in range(1, len(vs)-1):
            tri = [vs[0], vs[i], vs[i+1]]; tuv = [uv[0], uv[i], uv[i+1]]
            xs = [t.x*W for t in tuv]; ys = [t.y*H for t in tuv]
            x0 = max(0, int(min(xs))-1); x1 = min(W-1, int(max(xs))+1)
            y0 = max(0, int(min(ys))-1); y1 = min(H-1, int(max(ys))+1)
            den = (ys[1]-ys[2])*(xs[0]-xs[2]) + (xs[2]-xs[1])*(ys[0]-ys[2])
            if abs(den) < 1e-12 or x1 < x0 or y1 < y0: continue
            for py in range(y0, y1+1):
                for px in range(x0, x1+1):
                    gx, gy = px+0.5, py+0.5
                    l1 = ((ys[1]-ys[2])*(gx-xs[2]) + (xs[2]-xs[1])*(gy-ys[2]))/den
                    l2 = ((ys[2]-ys[0])*(gx-xs[2]) + (xs[0]-xs[2])*(gy-ys[2]))/den
                    l3 = 1.0 - l1 - l2
                    if l1 < -0.05 or l2 < -0.05 or l3 < -0.05: continue
                    p = MW @ (tri[0]*l1 + tri[1]*l2 + tri[2]*l3)
                    if not (xlo <= p.x <= xhi and ylo <= p.y <= yhi and zlo <= p.z <= zhi): continue
                    out.append((px, py, p))
    return out

def is_mouth(c):
    r, g, b = float(c[0]), float(c[1]), float(c[2])
    dark = (r > 0.20 and g < 0.40*r and b < 0.50*r)                 # 口の中の暗い赤
    tong = (r > 0.78 and 0.28 < g < 0.62 and abs(g-b) < 0.12)       # 舌の桃色
    return dark or tong

sme, simg, S, SW, SH = load(SRC)
dme, dimg, D, DW, DH = load(DST)
print("MT 元 %dx%d  先 %dx%d" % (SW, SH, DW, DH))

pts = []; cols = []
for px, py, p in scan(sme, S, SW, SH):
    c = S[py, px, :3]
    if is_mouth(c):
        pts.append(p); cols.append(c.copy())
print("MT 元の口の画素 %d" % len(pts))
if not pts:
    print("MT 口の色が見つからない"); sys.exit(1)
kd = kdtree.KDTree(len(pts))
for i, p in enumerate(pts): kd.insert(p, i)
kd.balance()

written = 0
for px, py, p in scan(dme, D, DW, DH):
    co, i, d = kd.find(p)
    if d > EPS: continue
    D[py, px, :3] = cols[i]; written += 1
print("MT 塗った画素 %d" % written)

out = bpy.data.images.new("mouth", DW, DH, alpha=True)
out.pixels = D.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save()
print("MT 書き出し", OUT)
