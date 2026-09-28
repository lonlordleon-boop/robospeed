# -*- coding: utf-8 -*-
"""キャラの顔から、目と口だけを「背景が透明な1枚の絵」として切り出す（顔のステッカー）。

   切り出した絵は mouthpaste.py で別のキャラの顔へ正面から貼る。
   3Dから3Dへ直接写すと途中の絵が残らないが、1枚の絵にしておけば、見て確かめたり、
   瞳の色を変えたり、どのキャラにも同じ絵を貼ったりできる。

   作り方: 顔の正面に格子を置き、画素ごとに正面から光線を当ててテクスチャの色をそのまま読む
   （画面に描いた絵は色の変換で灰色がかるので使わない）。
   透明度:
   - 目（まつ毛の先まで）と口の楕円の外は透明。
   - 楕円の中でも、肌の色に近い画素ほど透明にする（肌の色は範囲の中の肌らしい画素の中央値）。
   - 瞳の円の外にある髪の色（眉・前髪・横髪）は透明にする。瞳も茶色なので円の中は残す。
   骨は素の姿勢（バインド姿勢）に戻してから測る。目と口の位置もこの姿勢で測ったものを渡す。

   実行: blender -b --factory-startup -P facedecal.py --
         入力.glb 出力.png "左目x,z;右目x,z;口x,z" "x下限,x上限,z下限,z上限" 横の画素数
   出力.png のほかに、白い背景に載せた確認用の絵（_白.png）も書き出す。
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
PTS = np.array([[float(v) for v in p.split(',')] for p in a[2].split(';')])
X0, X1, Z0, Z1 = [float(v) for v in a[3].split(',')]
NW = int(a[4])
NH = int(round(NW * (Z1 - Z0) / (X1 - X0)))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
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

eL, eR, mo = PTS
mid = (eL + eR) / 2; ex = eR - eL; sp = np.linalg.norm(ex); ex /= sp
ey = np.array([ex[1], -ex[0]])
if np.dot(mo - mid, ey) < 0: ey = -ey
mu = float((mo - mid) @ ex / sp); mv = float((mo - mid) @ ey / sp)

def hsv(c):
    mx = c.max(-1); mn = c.min(-1); d = np.maximum(mx-mn, 1e-6)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    h = np.where(mx == r, ((g-b)/d) % 6, np.where(mx == g, (b-r)/d + 2, (r-g)/d + 4)) / 6.0
    return h, np.where(mx > 0, (mx-mn)/np.maximum(mx, 1e-6), 0), mx

RGB = np.zeros((NH, NW, 3), np.float32); HIT = np.zeros((NH, NW), bool)
U = np.zeros((NH, NW)); V = np.zeros((NH, NW))
for j in range(NH):
    z = Z1 - (j + 0.5) / NH * (Z1 - Z0)             # 上の行が先頭
    for i in range(NW):
        x = X0 + (i + 0.5) / NW * (X1 - X0)
        d = np.array([x, z]) - mid
        U[j, i] = d @ ex / sp; V[j, i] = d @ ey / sp
        loc, nrm, fi, dist = bvh.ray_cast(Vector((x, -5.0, z)), Vector((0, 1, 0)), 10.0)
        if loc is None: continue
        Q = P[TV[fi]]
        v0, v1 = Q[1]-Q[0], Q[2]-Q[0]; v2 = np.array(loc) - Q[0]
        d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1; d20, d21 = v2 @ v0, v2 @ v1
        den = d00*d11 - d01*d01
        if abs(den) < 1e-14: continue
        b1 = (d11*d20 - d01*d21) / den; b2 = (d00*d21 - d01*d20) / den; b0 = 1 - b1 - b2
        w = uv[TL[fi]]; p = b0*w[0] + b1*w[1] + b2*w[2]
        tx = min(TW-1, max(0, int(p[0]*TW))); ty = min(TH-1, max(0, int(p[1]*TH)))
        RGB[j, i] = TA[ty, tx, :3]; HIT[j, i] = True

inE = (((np.abs(U) - 0.5) / 0.56)**2 + (V / 0.42)**2) < 1.0
# 口の楕円は上下を詰める。上を広く取ると鼻の下の肌と頬の赤みが、細かいピンクの粒の帯になって残った
inM = (((U - mu) / 0.40)**2 + ((V - mv) / 0.24)**2) < 1.0
h, s, v = hsv(RGB)
skin = HIT & ((h > 0.90) | (h < 0.062)) & (s > 0.04) & (s < 0.5) & (v > 0.55)
smed = np.median(RGB[skin & (inE | inM)], 0)
dist = np.linalg.norm(RGB - smed, axis=-1)
alpha = np.clip((dist - 0.08) / 0.10, 0, 1)
alpha[~(HIT & (inE | inM))] = 0
outIris = inE & (((np.abs(U) - 0.5)**2 + (V - 0.02)**2) > 0.24**2)
hair = (h > 0.03) & (h < 0.13) & (s > 0.25) & (v > 0.2)
alpha[outIris & hair] = 0
# 小さく孤立した塊（横髪の影の筋、点）を消す。目と口より十分小さい塊だけ
from collections import deque
mask = alpha > 0.2
lab = np.zeros(mask.shape, np.int32); sizes = [0]; cur = 0
for j0 in range(NH):
    for i0 in range(NW):
        if not mask[j0, i0] or lab[j0, i0]: continue
        cur += 1; q = deque([(j0, i0)]); lab[j0, i0] = cur; n = 0
        while q:
            j, i = q.popleft(); n += 1
            for dj, di in ((1,0),(-1,0),(0,1),(0,-1)):
                jj, ii = j+dj, i+di
                if 0 <= jj < NH and 0 <= ii < NW and mask[jj, ii] and not lab[jj, ii]:
                    lab[jj, ii] = cur; q.append((jj, ii))
        sizes.append(n)
sizes = np.array(sizes); big = max(sizes)
small = sizes < max(300, 0.03 * big)
# 塊に属さない薄い画素（alpha 0.2 以下）は、近くの塊に付いている縁として残す
kill = small[lab] & (lab > 0)
alpha[kill] = 0
print("FD 塊 %d 個のうち、小さい塊 %d 個を消した" % (cur, int(small[1:].sum())))
print("FD 絵 %dx%d（%.1fmm/画素）  肌の中央値 %s  不透明な画素 %d" % (NW, NH, (X1-X0)/NW*1000, np.round(smed, 3), int((alpha > 0.5).sum())))

def save(arr, path):
    im = bpy.data.images.new("d", NW, NH, alpha=True)
    im.pixels = arr[::-1].ravel().tolist()               # Blender の画像は下の行が先頭
    im.filepath_raw = path; im.file_format = 'PNG'; im.save()
save(np.dstack([RGB, alpha]).astype(np.float32), OUT)
white = RGB * alpha[..., None] + (1 - alpha[..., None])
save(np.dstack([white, np.ones((NH, NW))]).astype(np.float32), os.path.splitext(OUT)[0] + "_白.png")
print("FD 書き出し", OUT)
