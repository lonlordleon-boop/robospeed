# -*- coding: utf-8 -*-
"""目を閉じた絵のテクスチャを作る。
   このモデルのテクスチャは面ごとに小さく散らばって並んでいるので、画像の上で目を探すことはできない。
   そこで、画素ごとに「その画素がモデルのどこに当たるか」を計算し、3次元の位置で塗り分ける。
   目の範囲は、まわりの肌の色でいったん塗りつぶし、その上に閉じたまぶたの線を描く。
   肌の色は、目のすぐ外側の画素から一番近いものを持ってくるので、陰影がつながる。
   実行: blender -b --factory-startup -P eyeclose.py -- 入力.glb 出力テクスチャ.png 目中心x,y,z 半径x,y,z まぶたz 反り 線の太さ"""
import bpy, sys
import numpy as np
from mathutils import Vector, kdtree

a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
CX, CY, CZ = [float(x) for x in a[2].split(',')]
RX, RY, RZ = [float(x) for x in a[3].split(',')]
ZLID = float(a[4]); ARC = float(a[5]); THICK = float(a[6])
GROW = 1.35                      # 肌の色を拾うための、ひとまわり大きい範囲

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
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
MW = me.matrix_world
print("EC テクスチャ %dx%d" % (W, H))

def dist(p, k):
    """左右どちらか近いほうの目の中心からの、半径で割った距離"""
    best = 9.9
    for sx in (1.0, -1.0):
        dx = (p.x - sx*CX)/(RX*k); dy = (p.y - CY)/(RY*k); dz = (p.z - CZ)/(RZ*k)
        d = (dx*dx + dy*dy + dz*dz) ** 0.5
        if d < best: best = d
    return best

def texels(f):
    """面が使っている画素と、その3次元の位置を返す"""
    vs = [mesh.vertices[v].co for v in f.vertices]
    uv = [uvl[li].uv for li in f.loop_indices]
    out = []
    for i in range(1, len(vs)-1):
        tri = [vs[0], vs[i], vs[i+1]]; tuv = [uv[0], uv[i], uv[i+1]]
        xs = [t.x*W for t in tuv]; ys = [t.y*H for t in tuv]   # 画素は下の行が先頭
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
                out.append((px, py, MW @ (tri[0]*l1 + tri[1]*l2 + tri[2]*l3)))
    return out

# 面の中心ではなく、画素ひとつずつの位置で内と外を決める。
# 面の中心で選ぶと、ふちの面がまるごと外れて、元の目の絵が三日月形に残ってしまう。
near = [f for f in mesh.polygons if dist(MW @ f.center, GROW*1.3) < 1.0]
inner_tx = []; pts = []; cols = []
for f in near:
    for px, py, p in texels(f):
        d = dist(p, 1.0)
        if d < 1.0:
            inner_tx.append((px, py, p))
        elif dist(p, GROW) < 1.0:
            c = A[py, px, :3]
            if c[0] < 0.55: continue                      # 髪やまつ毛の暗い色は除く
            # 白目・ハイライトは色味が無い（赤緑青がほぼ同じ）。肌は赤みがあるので、それで分ける
            if float(max(c) - min(c)) < 0.07: continue
            pts.append(p); cols.append(c)
print("EC まわりの面 %d 枚、目の画素 %d" % (len(near), len(inner_tx)))
# 肌の色の元から、外れた色（目の縁の影や白目のふちなど）を落とす。
# まん中あたりの色から離れているものを捨てると、塗ったあとに灰色の筋が出なくなる。
_C = np.array(cols, np.float32)
_med = np.median(_C, axis=0)
_keep = np.linalg.norm(_C - _med, axis=1) < 0.13
pts = [p for p, k in zip(pts, _keep) if k]
cols = [c for c, k in zip(cols, _keep) if k]
print("EC 肌の色の元 %d 画素（まん中の色 %s）" % (len(pts), np.round(_med, 3)))
kd = kdtree.KDTree(len(pts))
for i, p in enumerate(pts): kd.insert(p, i)
kd.balance()

LASH = np.array([0.10, 0.08, 0.09], np.float32)
painted = 0; lashed = 0
if True:
    for px, py, p in inner_tx:
        # 近いところ8点の平均にする。一番近い1点だけだと、筋のような模様が出る
        hits = kd.find_n(p, 8)
        skin = sum((cols[i] for (_, i, _) in hits), np.zeros(3, np.float32)) / max(1, len(hits))
        # 閉じたまぶたの線。中央がすこし持ち上がった弧にする
        t = (abs(p.x) - CX)/(RX*0.80)
        zl = ZLID + ARC*max(0.0, 1.0 - t*t)
        # 目じりに向かって細くし、目の幅から飛び出さないようにする
        th = THICK*max(0.0, 1.0 - t*t) if abs(t) < 1.0 else 0.0
        e = abs(p.z - zl)
        if th > 0.0 and e < th:
            w = min(1.0, (th - e)/(th*0.45))           # ふちをぼかす
            A[py, px, :3] = skin*(1-w) + LASH*w
            lashed += 1
        else:
            A[py, px, :3] = skin
        painted += 1
print("EC 塗った画素 %d（うち線 %d）" % (painted, lashed))

out = bpy.data.images.new("closed", W, H, alpha=True)
out.pixels = A.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save()
print("EC 書き出し", OUT)
