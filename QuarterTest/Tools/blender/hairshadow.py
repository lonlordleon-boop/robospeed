# -*- coding: utf-8 -*-
"""髪の房がかぶさる服に、髪の影を焼き込む（アンビエントオクルージョン）。形・骨・重み・動きはそのまま、絵だけ。
   お嬢様（小学生編）は、肩口で房のふちがぎざぎざに割れ、すき間から白い服が欠片のように見えた（「肩口の髪の欠けは両肩、特に右が酷い」）。
   形でふちをつなぎ直すのは、ふちが入り乱れていて無理だった。房に隠れた服を髪の色で塗ると、横から見て黒い帯が出る。
   1) 箱（左右の肩）の中の明るい面（服）の絵の画素を、STEP 画素のかたまりごとに 3D の位置と面の向きにする（素の姿勢）
   2) 面の上の半球へ K 本の光線（面の向きに寄せて散らす）を DIST まで飛ばし、髪（暗い面）に当たる割合 occ を出す
   3) 色 × (1 − STR × occ^GAM) にする。房がかぶさる所ほど暗く、かぶさらない所はほぼそのまま。影の境目はなだらか
   --mask で occ の絵（白いほど暗くする）を書く。--check で影を赤くした確かめ用の glb を書く（出力の絵は書かない）
   実行: blender -b --factory-startup -P hairshadow.py -- 入力.glb 出力.png [--str 0.8] [--dist 0.05] [--k 48] [--step 3] [--mask 絵.png] [--check 確かめ.glb]"""
import bpy, bmesh, sys, math, colorsys, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, default):
    global a
    if name in a: i = a.index(name); v = a[i+1]; a = a[:i] + a[i+2:]; return v
    return default
STR = float(opt('--str', 0.8)); DIST = float(opt('--dist', 0.05)); K = int(opt('--k', 48)); STEP = int(opt('--step', 3)); GAM = float(opt('--gam', 1.0))
MASK = opt('--mask', None); CHECK = opt('--check', None); TEX = opt('--tex', None)
SRC, OUT = a[0], a[1]
BOXES = [(-0.21, -0.05, -0.09, 0.10, 0.68, 0.87), (0.05, 0.21, -0.09, 0.10, 0.68, 0.87)]   # 右肩・左肩
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data; MW = me.matrix_world
img = bpy.data.images.load(TEX) if TEX else next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
def fv(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    return colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])[2]
V = np.array([fv(p) for p in m.polygons])
bm = bmesh.new(); bm.from_mesh(m); bm.transform(MW); bm.faces.ensure_lookup_table(); tree = BVHTree.FromBMesh(bm)
def inb(c): return any(b[0] <= c.x <= b[1] and b[2] <= c.y <= b[3] and b[4] <= c.z <= b[5] for b in BOXES)
# 半球の向き（面の向きに寄せる：cosine 重み。黄金角で散らす）
H0 = []
for k in range(K):
    t = (k + 0.5) / K; r = math.sqrt(t); ph = k * 2.39996
    H0.append(Vector((r * math.cos(ph), r * math.sin(ph), math.sqrt(max(0, 1 - t)))))
def occ_at(q, n):
    R = n.to_track_quat('Z', 'Y').to_matrix(); hit = 0
    for d0 in H0:
        d = R @ d0; h = tree.ray_cast(q + n * 0.0006, d, DIST)
        if h[0] is not None and V[h[2]] < 0.4: hit += 1
    return hit / K
res = px.copy(); occm = np.zeros((H_, W_), np.float32); nf = 0; npx = 0
for p in m.polygons:
    c = MW @ p.center
    if V[p.index] < 0.6 or not inb(c): continue
    uv = [uvl[li].uv[:] for li in p.loop_indices]; P = [bm.faces[p.index].verts[k].co for k in range(len(p.vertices))]
    n = bm.faces[p.index].normal.normalized()
    for k in range(1, len(uv) - 1):
        tri = np.array([uv[0], uv[k], uv[k+1]]) * [W_, H_]; T = (P[0], P[k], P[k+1])
        x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
        x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W_ - 1); y1 = min(y1, H_ - 1)
        if x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = tri; d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12: continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d; l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d; l3 = 1 - l1 - l2
        M = (l1 >= -0.03) & (l2 >= -0.03) & (l3 >= -0.03)
        if not M.any(): continue
        O = np.zeros(M.shape, np.float32)
        for by0 in range(0, M.shape[0], STEP):
            for bx0 in range(0, M.shape[1], STEP):
                blk = M[by0:by0+STEP, bx0:bx0+STEP]
                if not blk.any(): continue
                L1 = float(np.clip(l1[by0:by0+STEP, bx0:bx0+STEP][blk].mean(), 0, 1)); L2 = float(np.clip(l2[by0:by0+STEP, bx0:bx0+STEP][blk].mean(), 0, 1 - L1))
                q = T[0] * L1 + T[1] * L2 + T[2] * (1 - L1 - L2)
                O[by0:by0+STEP, bx0:bx0+STEP] = occ_at(q, n)
        sub = (slice(y0, y1 + 1), slice(x0, x1 + 1))
        om = occm[sub]; om[M] = np.maximum(om[M], O[M])
    nf += 1
# 影をかたまりの境目でなめらかに（3×3 の平均を 2 回。使っている画素だけ）
used = occm > 0
for _ in range(2):
    pad = np.pad(occm, 1); acc = np.zeros_like(occm)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1): acc += pad[1+dy:1+dy+H_, 1+dx:1+dx+W_]
    occm = np.where(used, np.maximum(occm, 0) * 0 + acc / 9, occm)
f = 1 - STR * np.clip(occm, 0, 1) ** GAM
if CHECK:
    res[..., 0] = np.where(used, res[..., 0] * f + (1 - f), res[..., 0]); res[..., 1] = np.where(used, res[..., 1] * f, res[..., 1]); res[..., 2] = np.where(used, res[..., 2] * f, res[..., 2])
else:
    res[..., :3] = np.where(used[..., None], res[..., :3] * f[..., None], res[..., :3])
print("HS 服の面 %d・影のある画素 %d（暗さ 0.3 以上 %d）" % (nf, int((occm > 0.02).sum()), int((STR * occm > 0.3).sum())))
if MASK:
    mk = np.zeros((H_, W_, 4), np.float32); mk[..., 3] = 1; mk[..., 0] = mk[..., 1] = mk[..., 2] = np.clip(occm, 0, 1)
    im = bpy.data.images.new("m", W_, H_, alpha=True); im.pixels = mk.ravel(); im.filepath_raw = MASK; im.file_format = 'PNG'; im.save(); print("HS マスク", MASK)
if CHECK:
    img0 = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
    img0.scale(W_, H_); img0.pixels = res.ravel(); img0.pack()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=CHECK, export_format='GLB', export_animations=False, export_skins=True, export_yup=True); print("HS 確かめ用", CHECK)
else:
    im = bpy.data.images.new("o", W_, H_, alpha=True); im.pixels = res.ravel(); im.filepath_raw = OUT; im.file_format = 'PNG'; im.save(); print("HS 書き出し", OUT)
