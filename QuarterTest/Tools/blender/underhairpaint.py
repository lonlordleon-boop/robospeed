# -*- coding: utf-8 -*-
"""髪のすき間からしか見えない服の所を、髪の色で塗る。形・骨・重み・動きはそのまま、絵だけ。
   お嬢様（小学生編）は、右肩のうしろ（首の付け根の横）で、髪の先が櫛のように細かく割れて肩の上に浮いていて、
   その間から白い服が見え、横・斜めうしろから見ると髪の中に白いかけらが散って見えた（「右肩の白いかけら」）。
   面ごとに塗ると、横から見て髪のふちの横に黒い帯が出る（前に言われた「肩にまだ髪が付いてる」になる）ので、絵の画素ごとに決める。
   1) 箱の中の明るい面（服）の絵の画素（STEP 画素ごと）の 3D の位置を出す（素の姿勢）
   2) 右・うしろ側のいろいろな向き（横の向き AZ0〜AZ1 度・上下 −10〜50 度）から見て、
      ・その点が見えない向きは数えない
      ・見える向きでは、画面の上下・左右に R ずらした 4 本の光線を飛ばし、左右の両方か上下の両方が髪（暗い面）に当たれば
        「すき間」、そうでなければ「ひらけて見える」
   3) ひらけて見える向きが 1 つもなく、すき間として見える向きがある画素だけ、髪の色（箱の中の暗い面の色の中央値）で塗る
   **塗る前に必ずマスクを見る**：--mask で塗る所だけ緑のマスクの絵を、--check で塗る所を緑にした確かめ用の glb を書き出す
   （--check のときは出力の絵を書かない）
   実行: blender -b --factory-startup -P underhairpaint.py -- 入力.glb 出力.png x0,x1,y0,y1,z0,z1
         [--az -200,-10] [--r 0.006] [--step 3] [--mask マスク.png] [--check 確かめ.glb]"""
import bpy, bmesh, sys, math, colorsys, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, default):
    global a
    if name in a: i = a.index(name); v = a[i+1]; a = a[:i] + a[i+2:]; return v
    return default
AZ0, AZ1 = map(float, opt('--az', '-200,-10').split(',')); RR = float(opt('--r', 0.006)); STEP = int(opt('--step', 3))
MASK = opt('--mask', None); CHECK = opt('--check', None)
SRC, OUT = a[0], a[1]; BOX = tuple(map(float, a[2].split(',')))
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data; MW = me.matrix_world
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data
def fcol(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    return px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
V = {p.index: colorsys.rgb_to_hsv(*fcol(p))[2] for p in m.polygons}
bm = bmesh.new(); bm.from_mesh(m); bm.transform(MW); bm.faces.ensure_lookup_table(); tree = BVHTree.FromBMesh(bm)
def inb(c): return BOX[0] <= c.x <= BOX[1] and BOX[2] <= c.y <= BOX[3] and BOX[4] <= c.z <= BOX[5]
DIRS = []   # 点からカメラへ向かう向き
for az in np.arange(AZ0, AZ1 + 0.1, 10):
    for el in (-10, 10, 30, 50):
        ar, er = math.radians(az), math.radians(el)
        DIRS.append(Vector((math.sin(ar) * math.cos(er), -math.cos(ar) * math.cos(er), math.sin(er))))
def hair_at(q, v):
    h = tree.ray_cast(q + v * 1.0, -v, 2.0)
    return h[0] is not None and V[h[2]] < 0.4
def classify(p, fi):
    ng = no = 0
    for v in DIRS:
        h = tree.ray_cast(p + v * 1.0, -v, 2.0)
        if h[0] is None or h[2] != fi and (h[0] - p).length > 0.002: continue   # その向きからは見えない
        u1 = v.cross(Vector((0, 0, 1))).normalized(); u2 = u1.cross(v).normalized()
        hs = [hair_at(p + u * s * RR, v) for u in (u1, u2) for s in (1, -1)]
        if (hs[0] and hs[1]) or (hs[2] and hs[3]): ng += 1
        else: no += 1
    return ng, no
tgt = []; dk = []
for f in bm.faces:
    c = f.calc_center_median()
    if not inb(c): continue
    if V[f.index] < 0.4: dk.append(f.index)
    elif V[f.index] >= 0.6: tgt.append(f.index)
hair = np.median(np.array([fcol(m.polygons[i]) for i in dk]), 0)
print("UH 箱の中の暗い面 %d・明るい面 %d・向き %d・髪の色 %s" % (len(dk), len(tgt), len(DIRS), tuple(round(float(x), 3) for x in hair)))
res = px.copy(); msk = np.zeros((H_, W_, 4), np.float32); msk[..., 3] = 1; npx = 0; nblk = 0; faces_hit = set()
for fi in tgt:
    p = m.polygons[fi]; uv = [uvl[li].uv[:] for li in p.loop_indices]; P = [bm.faces[fi].verts[k].co for k in range(len(p.vertices))]
    for k in range(1, len(uv) - 1):
        tri = np.array([uv[0], uv[k], uv[k+1]]) * [W_, H_]; T3 = (P[0], P[k], P[k+1])
        x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
        x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W_ - 1); y1 = min(y1, H_ - 1)
        (ax, ay), (bx, by), (cx, cy) = tri
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12: continue
        for by0 in range(y0, y1 + 1, STEP):
            for bx0 in range(x0, x1 + 1, STEP):
                ys, xs = np.mgrid[by0:min(by0 + STEP, y1 + 1), bx0:min(bx0 + STEP, x1 + 1)]
                xs_ = xs + 0.5; ys_ = ys + 0.5
                l1 = ((by - cy) * (xs_ - cx) + (cx - bx) * (ys_ - cy)) / d; l2 = ((cy - ay) * (xs_ - cx) + (ax - cx) * (ys_ - cy)) / d
                M = (l1 >= -0.05) & (l2 >= -0.05) & (1 - l1 - l2 >= -0.05)
                if not M.any(): continue
                # かたまりの真ん中の 3D の位置（面の中に収める）
                L1 = float(np.clip(l1[M].mean(), 0, 1)); L2 = float(np.clip(l2[M].mean(), 0, 1 - L1))
                q = T3[0] * L1 + T3[1] * L2 + T3[2] * (1 - L1 - L2)
                ng, no = classify(q, fi)
                if no == 0 and ng > 0:
                    res[ys[M], xs[M], :3] = (0, 1, 0) if CHECK else hair
                    msk[ys[M], xs[M], :3] = (0, 1, 0); npx += int(M.sum()); nblk += 1; faces_hit.add(fi)
print("UH %s（%d 画素・%d かたまり・%d 面）" % ('緑で印を付けた' if CHECK else '髪の色で塗った', npx, nblk, len(faces_hit)))
print("UH 面", ",".join(map(str, sorted(faces_hit))))
bm.free()
if MASK:
    im = bpy.data.images.new("m", W_, H_, alpha=True); im.pixels = msk.ravel(); im.filepath_raw = MASK; im.file_format = 'PNG'; im.save()
    print("UH マスク", MASK)
if CHECK:
    img.scale(W_, H_); img.pixels = res.ravel(); img.pack()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=CHECK, export_format='GLB', export_animations=False, export_skins=True, export_yup=True)
    print("UH 確かめ用", CHECK)
else:
    im = bpy.data.images.new("o", W_, H_, alpha=True); im.pixels = res.ravel(); im.filepath_raw = OUT; im.file_format = 'PNG'; im.save()
    print("UH 書き出し", OUT)
