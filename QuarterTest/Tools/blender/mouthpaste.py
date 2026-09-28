# -*- coding: utf-8 -*-
"""2Dで描いた口の絵を、素体の顔のテクスチャへ「3次元の位置」で貼り付ける。

   この素体は口を描かない三面図から生成してあるので、顔の口の位置はただの肌。
   そこへ口の絵を正面から投影して焼き込む。絵は別に作った1枚（開いた口・閉じた口など）。

   テクスチャは面ごとに散らばって並んでいるので、画像の上で口の場所は探せない。
   だから顔の正面にある面をひとつずつ取り、その面のUV三角形をテクスチャの画素に展開し、
   画素ごとに「モデルのどこに当たるか」（重心座標）を求めて、その x と z を口の絵の座標に直して色を拾う。
   絵の背景（既定はマゼンタ）に近い画素は透明として扱い、肌をそのまま残す。

   口の中心は world 座標で渡す（x, z）。前後 y は使わない（正面から投影するだけ）。
   顔の正面の面だけを対象にする（y が「前の限界」より小さいもの）。後頭部に写らないようにするため。

   出力はテクスチャの PNG と、そのテクスチャに差し替えた glb の両方。

   実行: blender -b --factory-startup -P mouthpaste.py --
         入力.glb 口の絵.png 出力テクスチャ.png 出力.glb 中心x,z 幅(m) 高さ(m)
         [前の限界y 既定-0.15] [背景色 r,g,b 0〜255 既定255,0,255] [メッシュ名 既定body]
   例:   ... -- doll.glb mouth_open.png tex_open.png doll_open.glb 0,0.745 0.13 0.075
"""
import bpy, sys, os
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DECAL, OUTPNG, OUTGLB = a[0], a[1], a[2], a[3]
CX, CZ = [float(v) for v in a[4].split(',')]
MW_, MH_ = float(a[5]), float(a[6])
YCUT = float(a[7]) if len(a) > 7 and a[7] else -0.15
KEY = np.array([float(v)/255.0 for v in a[8].split(',')]) if len(a) > 8 and a[8] else np.array([1.0, 0.0, 1.0])
MESHNAME = a[9] if len(a) > 9 and a[9] else 'body'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm and arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()
body = bpy.data.objects[MESHNAME]
mesh = body.data; uvl = mesh.uv_layers.active.data; MW = body.matrix_world
img = None
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)   # 下の行が先頭

# 口の絵。背景色との距離で透明度を作る（近いほど透明）
dimg = bpy.data.images.load(DECAL)
DW, DH = dimg.size
D = np.array(dimg.pixels[:], dtype=np.float32).reshape(DH, DW, 4)
D = D[::-1]                                                        # 上の行が先頭になるように返す
dist = np.linalg.norm(D[:, :, :3] - KEY[None, None, :], axis=2)
alpha = np.clip((dist - 0.20) / 0.30, 0.0, 1.0)
# 背景と口の色が混ざった縁の画素は、マゼンタが乗って紫っぽくなる。そこは透明度で薄めるだけにする
if D[:, :, 3].min() < 0.99:
    # 絵に透明度が入っていれば、それをそのまま使う（facedecal.py で切り出した目と口の絵など）
    alpha = D[:, :, 3].copy()
    print("MP 絵の透明度をそのまま使う")
print("MP 口の絵 %dx%d  不透明な画素 %.1f%%" % (DW, DH, 100.0*(alpha > 0.5).mean()))

P = np.array([tuple(MW @ v.co) for v in mesh.vertices])
# 対象の面: 全頂点が口の箱の中（余裕を持たせる）で、正面側
x0, x1 = CX - 0.8*MW_, CX + 0.8*MW_
z0, z1 = CZ - 0.8*MH_, CZ + 0.8*MH_
faces = []
for poly in mesh.polygons:
    vs = list(poly.vertices)
    Q = P[vs]
    if Q[:,0].min() < x0 or Q[:,0].max() > x1 or Q[:,2].min() < z0 or Q[:,2].max() > z1: continue
    if Q[:,1].max() > YCUT: continue
    faces.append(poly)
print("MP 対象の面 %d 枚（箱 x %.3f〜%.3f  z %.3f〜%.3f  y<%.2f）" % (len(faces), x0, x1, z0, z1, YCUT))

def tris_of(poly):
    loops = list(poly.loop_indices)
    # 四角形は扇で三角形に分ける
    for k in range(1, len(loops)-1):
        yield (loops[0], loops[k], loops[k+1])

# どれかの面に属する画素の地図。ふちの外 2 画素を塗るのは、どの面にも属さない隙間の画素だけにする。
# ふちを塗り残すと、描くときの補間で元の色が混ざり、舌や瞳に細いひびの線が出た
owned = np.zeros((H, W), dtype=bool)
for poly in mesh.polygons:
    for li in tris_of(poly):
        px = np.array([uvl[i].uv for i in li], dtype=np.float64) * np.array([W, H])
        x0_, x1_ = max(0, int(np.floor(px[:,0].min()))), min(W-1, int(np.ceil(px[:,0].max())))
        y0_, y1_ = max(0, int(np.floor(px[:,1].min()))), min(H-1, int(np.ceil(px[:,1].max())))
        if x1_ < x0_ or y1_ < y0_: continue
        (ax, ay), (bx, by), (cx_, cy) = px
        det = (bx-ax)*(cy-ay) - (cx_-ax)*(by-ay)
        if abs(det) < 1e-9: continue
        xs, ys = np.meshgrid(np.arange(x0_, x1_+1) + 0.5, np.arange(y0_, y1_+1) + 0.5)
        l1 = ((bx-xs)*(cy-ys) - (cx_-xs)*(by-ys)) / det
        l2 = ((cx_-xs)*(ay-ys) - (ax-xs)*(cy-ys)) / det
        ok = (l1 >= -1e-6) & (l2 >= -1e-6) & (1 - l1 - l2 >= -1e-6)
        owned[(ys[ok] - 0.5).astype(int), (xs[ok] - 0.5).astype(int)] = True

painted = 0
for poly in faces:
    for li in tris_of(poly):
        uv = np.array([uvl[i].uv for i in li], dtype=np.float64)
        wp = np.array([P[mesh.loops[i].vertex_index] for i in li], dtype=np.float64)
        px = uv * np.array([W, H])
        xmin, xmax = int(np.floor(px[:,0].min()))-2, int(np.ceil(px[:,0].max()))+2
        ymin, ymax = int(np.floor(px[:,1].min()))-2, int(np.ceil(px[:,1].max()))+2
        (ax, ay), (bx, by), (cx_, cy) = px
        det = (bx-ax)*(cy-ay) - (cx_-ax)*(by-ay)
        if abs(det) < 1e-9: continue
        # 辺ごとの高さ（重心座標を画素の距離に直すため）
        def hgt(p, q): return abs(det) / max(np.hypot(q[0]-p[0], q[1]-p[1]), 1e-9)
        t1, t2, t3 = 2.0/hgt(px[1], px[2]), 2.0/hgt(px[2], px[0]), 2.0/hgt(px[0], px[1])
        for yy in range(max(0, ymin), min(H-1, ymax)+1):
            for xx in range(max(0, xmin), min(W-1, xmax)+1):
                sx, sy = xx + 0.5, yy + 0.5
                l1 = ((bx-sx)*(cy-sy) - (cx_-sx)*(by-sy)) / det
                l2 = ((cx_-sx)*(ay-sy) - (ax-sx)*(cy-sy)) / det
                l3 = 1.0 - l1 - l2
                inside = l1 >= -1e-6 and l2 >= -1e-6 and l3 >= -1e-6
                if not inside:
                    if owned[yy, xx] or l1 < -t1 or l2 < -t2 or l3 < -t3: continue
                p = l1*wp[0] + l2*wp[1] + l3*wp[2]
                u = (p[0] - CX) / MW_ + 0.5
                v = (CZ - p[2]) / MH_ + 0.5
                if u < 0 or u >= 1 or v < 0 or v >= 1: continue
                di, dj = int(v*DH), int(u*DW)
                al = alpha[di, dj]
                if al <= 0.01: continue
                A[yy, xx, :3] = A[yy, xx, :3]*(1-al) + D[di, dj, :3]*al
                painted += 1
print("MP 塗った画素 %d" % painted)

img.pixels = A.ravel().tolist()
img.filepath_raw = OUTPNG; img.file_format = 'PNG'; img.save()
print("MP テクスチャ", OUTPNG)
# 書き出しが元の絵（glb に詰まっていたもの）をそのまま使ってしまうので、
# 保存した PNG を読み直して材質の絵を差し替える
newimg = bpy.data.images.load(OUTPNG)
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image == img: n.image = newimg
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUTGLB, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True, export_image_format='JPEG', export_jpeg_quality=92)
print("MP 書き出し", OUTGLB, os.path.getsize(OUTGLB))
