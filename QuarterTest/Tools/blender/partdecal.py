# -*- coding: utf-8 -*-
"""キャラの顔から、眉や鼻の点など小さな部品を「背景が透明な絵」として切り出す。

   facedecal.py（目と口）と同じく、顔の正面に格子を置いて光線でテクスチャの色を直接読む。骨は素の姿勢に戻す。
   透明度の決め方は2通り。
   - diff: 部品がある版（入力A）と、部品を消した版（入力B）の色の差。眉は前髪と色がほぼ同じなので、
           肌との色の差では前髪まで拾ってしまう。faceerase.py で眉だけ消した版との差なら、眉の形だけが出る。
   - skin: 範囲の中の肌の色（中央値）からの離れ具合。鼻の点のように、まわりが肌だけの部品に使う。
   色を指定すると、形（透明度）はそのままに、色だけを置き換える（眉を髪の色にする）。
   明るさの濃淡は元の絵から少し残す。
   小さく孤立した塊は消し、大きい順に指定の数だけ残す。

   実行: blender -b --factory-startup -P partdecal.py --
         入力A.glb 出力.png "x下限,x上限,z下限,z上限" 横の画素数 diff|skin
         [入力B.glb（diff のとき）] [塗る色 r,g,b（省略で元の色）] [残す塊の数 既定1]
   出力.png のほかに、白い背景に載せた確認用の絵（_白.png）も書き出す。
"""
import bpy, sys, os
import numpy as np
from collections import deque
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--")+1:]
SRCA, OUT = a[0], a[1]
X0, X1, Z0, Z1 = [float(v) for v in a[2].split(',')]
NW = int(a[3]); NH = int(round(NW * (Z1 - Z0) / (X1 - X0)))
MODE = a[4]
SRCB = a[5] if len(a) > 5 and a[5] else None
COLOR = np.array([float(v) for v in a[6].split(',')], np.float32) if len(a) > 6 and a[6] else None
NKEEP = int(a[7]) if len(a) > 7 and a[7] else 1

def sample(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    if arm:
        if arm.animation_data: arm.animation_data.action = None
        for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    me = next(o for o in bpy.data.objects if o.type == 'MESH')
    mesh = me.data; mesh.calc_loop_triangles()
    dg = bpy.context.evaluated_depsgraph_get(); oe = me.evaluated_get(dg); em = oe.to_mesh()
    P = np.array([tuple(me.matrix_world @ v.co) for v in em.vertices]); oe.to_mesh_clear()
    uv = np.array([tuple(l.uv) for l in mesh.uv_layers.active.data])
    TL = np.array([tuple(t.loops) for t in mesh.loop_triangles]); TV = np.array([tuple(t.vertices) for t in mesh.loop_triangles])
    img = next(n.image for m in mesh.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
    TW, TH = img.size
    TA = np.array(img.pixels[:], dtype=np.float32).reshape(TH, TW, 4)
    bvh = BVHTree.FromPolygons([Vector(p) for p in P], [tuple(t) for t in TV])
    RGB = np.ones((NH, NW, 3), np.float32); HIT = np.zeros((NH, NW), bool)
    for j in range(NH):
        z = Z1 - (j + 0.5) / NH * (Z1 - Z0)
        for i in range(NW):
            x = X0 + (i + 0.5) / NW * (X1 - X0)
            loc, nrm, fi, dist = bvh.ray_cast(Vector((x, -5.0, z)), Vector((0, 1, 0)), 10.0)
            if loc is None: continue
            Q = P[TV[fi]]; v0, v1 = Q[1]-Q[0], Q[2]-Q[0]; v2 = np.array(loc) - Q[0]
            d00, d01, d11 = v0@v0, v0@v1, v1@v1; d20, d21 = v2@v0, v2@v1; den = d00*d11 - d01*d01
            if abs(den) < 1e-14: continue
            b1 = (d11*d20 - d01*d21)/den; b2 = (d00*d21 - d01*d20)/den; b0 = 1 - b1 - b2
            w = uv[TL[fi]]; p = b0*w[0] + b1*w[1] + b2*w[2]
            RGB[j, i] = TA[min(TH-1, max(0, int(p[1]*TH))), min(TW-1, max(0, int(p[0]*TW))), :3]; HIT[j, i] = True
    return RGB, HIT

RA, HA = sample(SRCA)
if MODE == 'diff':
    RB, HB = sample(SRCB)
    alpha = np.clip((np.linalg.norm(RA - RB, axis=-1) - 0.05) / 0.12, 0, 1) * HA
else:
    mx = RA.max(-1); mn = RA.min(-1); s = (mx - mn) / np.maximum(mx, 1e-6)
    skin = HA & (mx > 0.55) & (s > 0.04) & (s < 0.5)
    med = np.median(RA[skin], 0)
    alpha = np.clip((np.linalg.norm(RA - med, axis=-1) - 0.07) / 0.08, 0, 1) * HA
    print("PD 肌の中央値", np.round(med, 3))

# 大きい塊だけ残す
m = alpha > 0.25; lab = np.zeros(m.shape, np.int32); sizes = [0]; cur = 0
for j0, i0 in zip(*np.nonzero(m)):
    if lab[j0, i0]: continue
    cur += 1; q = deque([(j0, i0)]); lab[j0, i0] = cur; c = 0
    while q:
        j, i = q.popleft(); c += 1
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                jj, ii = j+dj, i+di
                if 0 <= jj < NH and 0 <= ii < NW and m[jj, ii] and not lab[jj, ii]:
                    lab[jj, ii] = cur; q.append((jj, ii))
    sizes.append(c)
order = [o for o in np.argsort(sizes)[::-1][:NKEEP] if o > 0]
keep = np.isin(lab, order)
grow = keep.copy()
for _ in range(2):
    g = grow.copy(); g[1:] |= grow[:-1]; g[:-1] |= grow[1:]; g[:, 1:] |= grow[:, :-1]; g[:, :-1] |= grow[:, 1:]; grow = g
alpha[~grow] = 0
print("PD 塊 %d 個 → 残した大きさ %s" % (cur, [sizes[o] for o in order]))

RGB = RA.copy()
if COLOR is not None:
    # 形はそのまま、色だけ置き換える。元の明るさの濃淡を 3 割だけ残す
    lum = RA.mean(-1); core = alpha > 0.6
    ref = np.median(lum[core]) if core.any() else 0.5
    shade = np.clip(1 + 0.3 * (lum - ref), 0.7, 1.3)[..., None]
    RGB = np.clip(COLOR[None, None, :] * shade, 0, 1)
print("PD 絵 %dx%d（%.2fmm/画素）  不透明な画素 %d" % (NW, NH, (X1-X0)/NW*1000, int((alpha > 0.5).sum())))

def save(arr, path):
    im = bpy.data.images.new("d", NW, NH, alpha=True)
    im.pixels = arr[::-1].ravel().tolist()
    im.filepath_raw = path; im.file_format = 'PNG'; im.save()
save(np.dstack([RGB, alpha]).astype(np.float32), OUT)
white = RGB * alpha[..., None] + (1 - alpha[..., None])
save(np.dstack([white, np.ones((NH, NW))]).astype(np.float32), os.path.splitext(OUT)[0] + "_白.png")
print("PD 書き出し", OUT)
