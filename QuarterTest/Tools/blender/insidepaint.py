# -*- coding: utf-8 -*-
"""貼り直し（retexture）で白く塗られてしまった「内側の面」を、まわりの色で塗り直す。

   meshy_v5_retexture は三面図に写っている面しか塗れない。カツラの内側のように
   どの向きからも見えない面は、白や薄い灰色で埋められる。そのままだと、
   髪をかぶせたときに後頭部が白く光って見える。

   貼り直す前のモデル（見本）を一緒に渡す。面の並びは貼り直しで変わらないので、
   「見本では色が付いているのに、貼り直し後は白い」面だけを内側とみなす。
   見本がもともと白い面（白い靴下など）は触らない。

   塗る色は、内側でない面の画素のうち、3次元で近いものの平均。陰影ごと借りる。
   テクスチャは面ごとにバラバラに並んでいるので、画像の上ではなく位置で選ぶ。
   Blender の画像は下の行が先頭。UV の v はそのまま行番号に使う。

   実行: blender -b --factory-startup -P insidepaint.py -- 貼り直した.glb 見本.glb 出力.png [鮮やかさ上限 既定0.18] [明るさ下限 既定0.62]
   そのあと swaptex.py で GLB に戻す。
"""
import bpy, sys, colorsys
import numpy as np
from mathutils import kdtree

a = sys.argv[sys.argv.index("--")+1:]
SRC, MASK, OUT = a[0], a[1], a[2]
SAT = float(a[3]) if len(a) > 3 else 0.18      # これ未満の鮮やかさで
VAL = float(a[4]) if len(a) > 4 else 0.62      # これ以上の明るさなら「白く塗られた」とみなす

bpy.ops.wm.read_factory_settings(use_empty=True)

def load(path):
    before = set(o.name for o in bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    news = [o for o in bpy.data.objects if o.name not in before]
    me = [o for o in news if o.type == 'MESH' and not o.name.startswith("Icosphere")][0]
    img = None
    for m in me.data.materials:
        if not m or not m.use_nodes: continue
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
    W, H = img.size
    A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    return me, A, W, H

me, A, W, H = load(SRC)
mk, B, MW_, MH = load(MASK)
uvl = me.data.uv_layers.active.data
uvm = mk.data.uv_layers.active.data
mesh = me.data
MW = me.matrix_world
print("IP テクスチャ %dx%d、見本 %dx%d、面 %d / %d" % (W, H, MW_, MH, len(mesh.polygons), len(mk.data.polygons)))
if len(mesh.polygons) != len(mk.data.polygons):
    print("IP 【注意】面の数が違う。並びで照合できない"); sys.exit(1)

def face_color(f, uvs, img, w, h):
    uv = [uvs[li].uv for li in f.loop_indices]
    cx = sum(u.x for u in uv)/len(uv); cy = sum(u.y for u in uv)/len(uv)
    return img[min(h-1, int(cy*h)), min(w-1, int(cx*w)), :3]

inside = []
for i, f in enumerate(mesh.polygons):
    c = face_color(f, uvl, A, W, H)
    h1, s1, v1 = colorsys.rgb_to_hsv(float(c[0]), float(c[1]), float(c[2]))
    if not (s1 < SAT and v1 > VAL): continue
    d = face_color(mk.data.polygons[i], uvm, B, MW_, MH)
    h2, s2, v2 = colorsys.rgb_to_hsv(float(d[0]), float(d[1]), float(d[2]))
    if s2 < SAT and v2 > VAL: continue        # 見本でも白い面は、もともと白いので触らない
    inside.append(i)
print("IP 内側とみなした面 %d 枚" % len(inside))
if not inside:
    print("IP 直すところが無い"); sys.exit(0)

def texels(f):
    """面が使っている画素と、その3次元の位置を返す"""
    vs = [mesh.vertices[v].co for v in f.vertices]
    uv = [uvl[li].uv for li in f.loop_indices]
    out = []
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
                out.append((px, py, MW @ (tri[0]*l1 + tri[1]*l2 + tri[2]*l3)))
    return out

ins = set(inside)
good_col = []; good_pos = []
for i, f in enumerate(mesh.polygons):
    if i in ins: continue
    for px, py, p in texels(f):
        good_col.append(A[py, px, :3]); good_pos.append(p)
print("IP 色の元になる画素 %d 個" % len(good_pos))
kd = kdtree.KDTree(len(good_pos))
for i, p in enumerate(good_pos): kd.insert(p, i)
kd.balance()

n = 0
for i in inside:
    for px, py, p in texels(mesh.polygons[i]):
        hits = kd.find_n(p, 8)          # 近い8画素の平均。1点だと筋模様が出る
        if not hits: continue
        A[py, px, :3] = sum((good_col[j] for (_, j, _) in hits), np.zeros(3, np.float32)) / len(hits)
        n += 1
print("IP 塗った画素 %d 個" % n)

out = bpy.data.images.new("painted", W, H, alpha=True)
out.pixels = A.ravel().tolist()
out.filepath_raw = OUT; out.file_format = 'PNG'; out.save()
print("IP 書き出し", OUT)
