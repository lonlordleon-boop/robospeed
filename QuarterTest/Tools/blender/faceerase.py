# -*- coding: utf-8 -*-
"""顔の目と口を消して、鼻・眉・頬の赤みを残す（のっぺらぼう＋鼻＋眉）。
   眉も消したいときは最後の引数に 1 を渡す（既定は残す）。

   新キャラの三面図の下絵にするため。目・眉・口の位置は facecopy.py と同じく、
   正面から見た左目・右目・口の中心（world の x, z、骨で変形したあと）で渡す。
   目の軸を u、口へ向かう向きを v とし、目の間隔で割った枠で消す範囲を決める。

   消し方: 消す範囲のまわりの肌の画素を集めておき、消す画素ごとに近い肌の色を
   距離の重みで混ぜて塗る（逆距離加重）。一色でべた塗りすると、頬の赤みや陰影と境目ができる。

   - 目と口: 範囲の中は全部塗り直す。
   - 眉: 前髪に掛かっている。前髪まで塗らないように、三角形ごとに色の中央値を見て、
     肌の三角形（おでこ）の中の、肌でない画素（眉の線）だけ塗り直す。
   - 鼻の点は口の楕円の上の縁より上にあるので残る。

   実行: blender -b --factory-startup -P faceerase.py --
         入力.glb 出力テクスチャ.png 出力.glb "左目x,z;右目x,z;口x,z" [眉も消す 1/0 既定0]
"""
import bpy, sys, os
import numpy as np
from mathutils import kdtree

a = sys.argv[sys.argv.index("--")+1:]
SRC, OUTPNG, OUTGLB = a[0], a[1], a[2]
DP = np.array([[float(v) for v in p.split(',')] for p in a[3].split(';')])
ERASEBROW = len(a) > 4 and a[4] == '1'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm and arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH')
mesh = me.data; mesh.calc_loop_triangles()
MW = me.matrix_world
# 骨で変形したあとの位置（アニメを外しても骨に姿勢が残っているため）
dg = bpy.context.evaluated_depsgraph_get(); oe = me.evaluated_get(dg); em = oe.to_mesh()
P = np.array([tuple(MW @ v.co) for v in em.vertices], dtype=np.float64)
oe.to_mesh_clear()
uv = np.array([tuple(l.uv) for l in mesh.uv_layers.active.data], dtype=np.float64)
TL = np.array([tuple(t.loops) for t in mesh.loop_triangles], dtype=np.int64)
TV = np.array([tuple(t.vertices) for t in mesh.loop_triangles], dtype=np.int64)
img = None
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
W, H = img.size
A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)   # 下の行が先頭
A0 = A.copy()

eL, eR, mo = DP
mid = (eL + eR) / 2; ex = eR - eL; sp = np.linalg.norm(ex); ex /= sp
ey = np.array([ex[1], -ex[0]])
if np.dot(mo - mid, ey) < 0: ey = -ey
def frame(xz):
    d = xz - mid
    return d @ ex / sp, d @ ey / sp
mu, mv = [float(t[0]) for t in frame(mo[None])]
print("FE 目の間隔 %.3f m  口 u %.2f v %.2f" % (sp, mu, mv))

# 消す範囲（u, v の楕円）。値は 1 未満が中
def r_eye(u, v):   return np.sqrt(((np.abs(u)-0.5)/0.56)**2 + (v/0.42)**2)
def r_brow(u, v):  return np.sqrt(((np.abs(u)-0.52)/0.40)**2 + ((v+0.58)/0.20)**2)
def r_mouth(u, v): return np.sqrt(((u-mu)/0.42)**2 + ((v-(mv+0.01))/0.24)**2)

def hsv(c):
    mx = c.max(1); mn = c.min(1); d = np.maximum(mx-mn, 1e-6)
    r, g, b = c[:, 0], c[:, 1], c[:, 2]
    h = np.where(mx == r, ((g-b)/d) % 6, np.where(mx == g, (b-r)/d + 2, (r-g)/d + 4)) / 6.0
    s = np.where(mx > 0, (mx-mn)/np.maximum(mx, 1e-6), 0)
    return h, s, mx
def skinlike(c):
    h, s, v = hsv(c)
    return ((h > 0.90) | (h < 0.062)) & (s > 0.04) & (s < 0.5) & (v > 0.55)

def tri_pixels(uvt, tol):
    px = uvt * np.array([W, H])
    x0, x1 = int(np.floor(px[:, 0].min())), int(np.ceil(px[:, 0].max()))
    y0, y1 = int(np.floor(px[:, 1].min())), int(np.ceil(px[:, 1].max()))
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(W-1, x1), min(H-1, y1)
    if x1 < x0 or y1 < y0: return None
    xs, ys = np.meshgrid(np.arange(x0, x1+1), np.arange(y0, y1+1))
    sx, sy = xs.ravel() + 0.5, ys.ravel() + 0.5
    (ax, ay), (bx, by), (cx, cy) = px
    det = (bx-ax)*(cy-ay) - (cx-ax)*(by-ay)
    if abs(det) < 1e-9: return None
    l1 = ((bx-sx)*(cy-sy) - (cx-sx)*(by-sy)) / det
    l2 = ((cx-sx)*(ay-sy) - (ax-sx)*(cy-sy)) / det
    l3 = 1 - l1 - l2
    # ふちの外 tol 画素まで含める。重心座標は「辺までの距離 ÷ 高さ」なので、辺ごとに高さで割って換算する。
    # 描くときは画素を補間して読むので、ふちの1〜2画素を塗り残すと元の目の線が薄く透けて見えた
    area2 = abs(det)
    def hgt(p, q): return area2 / max(np.hypot(q[0]-p[0], q[1]-p[1]), 1e-9)
    h1, h2, h3 = hgt(px[1], px[2]), hgt(px[2], px[0]), hgt(px[0], px[1])
    ok = (l1 >= -tol/h1) & (l2 >= -tol/h2) & (l3 >= -tol/h3)
    return ys.ravel()[ok], xs.ravel()[ok], np.stack([l1[ok], l2[ok], l3[ok]], 1)

# どの三角形にも属する画素の地図。ふちの外を塗るのは、どの三角形にも属さない隙間の画素だけにする。
# 隣に並んだ別の三角形の画素まで上書きすると、放射状の筋になった
owned = np.zeros((H, W), dtype=bool)
for t in range(len(TV)):
    r = tri_pixels(uv[TL[t]], 0.0)
    if r is not None: owned[r[0], r[1]] = True
print("FE 三角形に属する画素 %.1f%%" % (100.0*owned.mean()))

def hairlike(c):
    h, s, v = hsv(c)
    return (h > 0.05) & (h < 0.13) & (s > 0.45) & (v > 0.6)

# 顔の正面の三角形を集め、画素ごとの位置を求める
todo = []
ring = []      # 肌の見本 (x, z, 色)
allskin = []   # 消す範囲の中も含めた肌の画素の位置（眉と前髪の見分けに使う）
for t in range(len(TV)):
    Q = P[TV[t]]
    if Q[:, 1].max() > -0.05: continue
    n = np.cross(Q[1]-Q[0], Q[2]-Q[0])
    if n[1] >= 0: continue
    u_, v_ = frame(Q[:, [0, 2]])
    near = min(r_eye(u_, v_).min(), r_brow(u_, v_).min(), r_mouth(u_, v_).min())
    if near > 1.8: continue
    r0 = tri_pixels(uv[TL[t]], 0.0)
    r = tri_pixels(uv[TL[t]], 2.0)
    if r is None or r0 is None: continue
    ys, xs, L = r
    own = np.zeros(len(ys), dtype=bool)
    if len(r0[0]):
        key0 = set(zip(r0[0].tolist(), r0[1].tolist()))
        own = np.array([(y, x) in key0 for y, x in zip(ys.tolist(), xs.tolist())])
    keep = own | ~owned[ys, xs]
    ys, xs, L = ys[keep], xs[keep], L[keep]
    if not len(ys): continue
    wp = L @ P[TV[t]]; xz = wp[:, [0, 2]]
    pu, pv = frame(xz)
    col = A0[ys, xs, :3]
    # 前髪の三角形か: 画素の6割以上が髪の色なら前髪とみなし、眉消しの対象にしない
    tri_skin = hairlike(col).mean() < 0.6
    re, rb, rm = r_eye(pu, pv), r_brow(pu, pv), r_mouth(pu, pv)
    inside = (re < 1.05) | (rm < 1.05) | (rb < 1.0)
    # 見本: 消す範囲の外で、肌の画素。灰色がかった画素（まつ毛の影・目のまわり）は外す
    _, s_c, _ = hsv(col)
    sk_all = skinlike(col) & (s_c > 0.12)
    sk = sk_all & ~inside
    for k in np.nonzero(sk)[0]:
        ring.append((xz[k, 0], xz[k, 1], col[k]))
    for k in np.nonzero(sk_all)[0]:
        allskin.append((xz[k, 0], xz[k, 1]))
    zone = (np.abs(pu) < 0.95) & (pv > -0.45) & (pv < mv + 0.30)
    if inside.any() or zone.any():
        todo.append((ys, xs, pu, pv, xz, re, rb, rm, tri_skin, col))

print("FE 肌の見本 %d 画素" % len(ring))
# 肌の色の地図を x,z の 2mm 格子で作り、ガウスでぼかして穴を埋める（重み付きのぼかし）。
# いちばん近い見本の色を伸ばすと、ふちの色むらが放射状の筋になった
RX = np.array([r_[0] for r_ in ring]); RZ = np.array([r_[1] for r_ in ring]); RC = np.array([r_[2] for r_ in ring])
CELL = 0.002
gx0, gz0 = RX.min() - 0.05, RZ.min() - 0.05
GW, GH = int((RX.max() + 0.05 - gx0) / CELL) + 1, int((RZ.max() + 0.05 - gz0) / CELL) + 1
ix = ((RX - gx0) / CELL).astype(int); iz = ((RZ - gz0) / CELL).astype(int)
acc = np.zeros((GH, GW, 3)); wsum = np.zeros((GH, GW))
np.add.at(acc, (iz, ix), RC); np.add.at(wsum, (iz, ix), 1.0)
def blur(g, sig_m):
    s = sig_m / CELL
    kr = int(3 * s); kx = np.arange(-kr, kr+1); ker = np.exp(-0.5 * (kx / s)**2)
    g = np.apply_along_axis(lambda r: np.convolve(r, ker, mode='same'), 1, g)
    return np.apply_along_axis(lambda r: np.convolve(r, ker, mode='same'), 0, g)
# 目の範囲は幅 10cm ほどあり、細いぼかしでは中まで色が届かず黒く抜けた。
# 太いぼかしから順に重ね、見本が近くにある所ほど細いぼかしの色を使う
FILL = None
for sig in (0.06, 0.03, 0.012):
    ws = blur(wsum, sig)
    F = np.stack([blur(acc[:, :, c], sig) for c in range(3)], 2) / np.maximum(ws, 1e-9)[:, :, None]
    ref = np.median(ws[ws > 1e-6])
    conf = np.clip(ws / (0.3 * ref), 0, 1)[:, :, None]
    FILL = F if FILL is None else FILL * (1 - conf) + F * conf
print("FE 肌の地図 %dx%d" % (GW, GH))
# 眉と前髪は色がほぼ同じ（色相 0.064 と 0.070）で、色では分けられない。
# 眉は細い線なので、同じ縦の列を少し上にたどっても下にたどっても肌がある。前髪は上にたどると髪が続く
OCC = np.zeros((GH, GW), dtype=bool)
for x, z in allskin:
    i, j = int((z - gz0) / CELL), int((x - gx0) / CELL)
    if 0 <= i < GH and 0 <= j < GW: OCC[i, j] = True
def is_brow(x, z):
    i, j = int((z - gz0) / CELL), int((x - gx0) / CELL)
    # 眉の太さは 9mm ほど。上下とも 4〜14mm の範囲に肌が2マス以上あるものだけ眉とみなす。
    # 範囲を 22mm まで広げたら、前髪の毛先の上に見える肌まで拾い、前髪が削れた
    if not (0 <= j < GW): return False
    up = OCC[min(GH, i+2):min(GH, i+8), j].sum() >= 2
    dn = OCC[max(0, i-7):max(0, i-1), j].sum() >= 2
    return up and dn
def fill_at(x, z):
    fx = min(max((x - gx0) / CELL, 0), GW - 1.001); fz = min(max((z - gz0) / CELL, 0), GH - 1.001)
    i0, j0 = int(fz), int(fx); a_, b_ = fz - i0, fx - j0
    return (FILL[i0, j0]*(1-a_)*(1-b_) + FILL[i0, j0+1]*(1-a_)*b_ +
            FILL[i0+1, j0]*a_*(1-b_) + FILL[i0+1, j0+1]*a_*b_)

painted = 0
for ys, xs, pu, pv, xz, re, rb, rm, tri_skin, col in todo:
    for k in range(len(ys)):
        # 目と口: 0.9 までは全部、1.05 までぼかす
        w_em = np.clip((1.05 - min(re[k], rm[k])) / 0.15, 0, 1)
        w = w_em
        # 眉: おでこの三角形の中の、肌でない画素だけ（眉も消すと指定したときだけ）
        if ERASEBROW and rb[k] < 1.0 and not skinlike(col[k][None])[0] and is_brow(xz[k, 0], xz[k, 1]):
            w = 1.0
        c = fill_at(xz[k, 0], xz[k, 1])
        # 頬や口のまわりに残った小さな黒い点（元の絵のしみ）: 肌の地図より大きく暗い画素だけ塗る
        if w <= 0 and tri_skin and abs(pu[k]) < 0.95 and -0.45 < pv[k] < mv + 0.30:
            if col[k].max() < c.max() - 0.22:
                w = 1.0
        if w <= 0: continue
        A[ys[k], xs[k], :3] = A0[ys[k], xs[k], :3] * (1-w) + c * w
        painted += 1
print("FE 塗り直した画素 %d" % painted)

img.pixels = A.ravel().tolist()
img.filepath_raw = OUTPNG; img.file_format = 'PNG'; img.save()
print("FE テクスチャ", OUTPNG)
# 書き出しが glb に詰まっていた元の絵をそのまま使うので、保存した PNG を読み直して差し替える
newimg = bpy.data.images.load(OUTPNG)
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image == img: n.image = newimg
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUTGLB, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True, export_image_format='JPEG', export_jpeg_quality=92)
print("FE 書き出し", OUTGLB, os.path.getsize(OUTGLB))
