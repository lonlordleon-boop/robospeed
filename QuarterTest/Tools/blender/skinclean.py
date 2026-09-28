# -*- coding: utf-8 -*-
"""のっぺらぼうの顔の肌を、肌の色でそろえる（生成や貼り直しが残した目の線・口の汚れ・白い点を消す）。

   わんぱく少女の顔には、目の高さの細い線、口の位置の灰色の汚れ、あごの白っぽい跡、細かい白い点々が残っていた。
   lineerase.py は「まわりより暗い画素」だけを塗るので、白い汚れは消えない。

   箱の中の顔の前面の三角形ごとに、絵の画素を次のように分ける。
   ・赤い画素（頬の赤み・鼻の色）… 残す。肌より赤みが「赤みの差」以上強いもの
   ・髪 … 三角形の中で髪の色に近い画素が半分以上あれば、その髪の色の画素は残す（前髪のふち）
     最初は 25% にしたが、小さな細い三角形の先が絵の上で髪の画素にかかっていて、それが髪として残り、目の高さに細い線が出た
   ・それ以外 … 肌の色にする
   肌の色は、箱の中の肌の画素の中央値。箱のふち（幅の 20%）では元の色へ段々に戻す。
   頬の赤みのふちは、元の肌との中間の色になっているので、そのまま残る（肌の色とほぼ同じなので段差は出ない）。

   位置は素の姿勢の Blender 座標（x 左右、y 奥行き（前がマイナス）、z 上）。
   実行: blender -b --factory-startup -P skinclean.py -- 入力.glb 出力.png x0,x1,z0,z1,y上限 [赤みの差 0.03] [髪r,g,b 0〜1] [内側の箱 x0,x1,z0,z1]
"""
import bpy, sys
import numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
X0, X1, Z0, Z1, YMAX = [float(v) for v in a[2].split(',')]
RED = float(a[3]) if len(a) > 3 and a[3] else 0.03
HAIR = np.array([float(v) for v in a[4].split(',')]) if len(a) > 4 and a[4] else None
# 内側の箱（x0,x1,z0,z1）。この中では色の割合ではなく「顔の面の上にあるか」で肌か髪かを決める。
# 目の線は細長い三角形の中に描かれていて、暗い画素が半分を超え、色の割合では髪と判定されて残った。
# 前髪は顔の面より手前に浮いているので、面からの距離で分けられる
INNER = [float(v) for v in a[5].split(',')] if len(a) > 5 and a[5] else None
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if arm:
    if arm.animation_data: arm.animation_data.action = None
    for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
me = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
MW = me.matrix_world
P = np.array([tuple(MW @ v.co) for v in em.vertices])
mat = me.active_material
img = next(n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W, H = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
orig = px.copy()
uvl = em.uv_layers.active.data
em.calc_loop_triangles()

# 箱の中の前面の三角形と、その画素
tris = []
for t in em.loop_triangles:
    c = P[list(t.vertices)].mean(0)
    if not (X0 <= c[0] <= X1 and Z0 <= c[2] <= Z1 and c[1] <= YMAX): continue
    uv = np.array([uvl[li].uv for li in t.loops], dtype=np.float64)
    tris.append((t, uv, P[list(t.vertices)]))
def pixels_of(uv, ext=0.0):
    xs = uv[:, 0] * W; ys = uv[:, 1] * H
    pad = 1 + int(np.ceil(ext))
    x0 = max(0, int(np.floor(xs.min())) - pad); x1 = min(W - 1, int(np.ceil(xs.max())) + pad)
    y0 = max(0, int(np.floor(ys.min())) - pad); y1 = min(H - 1, int(np.ceil(ys.max())) + pad)
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
    if abs(d) < 1e-12: return None
    l1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d
    l2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d
    l3 = 1 - l1 - l2
    m = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
    if ext > 0:
        # 辺からの距離（画素）で、辺の外 ext 画素までを含めた範囲
        area2 = abs(d)
        L = [np.hypot(xs[1] - xs[2], ys[1] - ys[2]), np.hypot(xs[2] - xs[0], ys[2] - ys[0]), np.hypot(xs[0] - xs[1], ys[0] - ys[1])]
        alt = [area2 / max(Lk, 1e-9) for Lk in L]
        mx = (l1 * alt[0] >= -ext) & (l2 * alt[1] >= -ext) & (l3 * alt[2] >= -ext)
        return x0, x1, y0, y1, m, l1, l2, l3, mx
    return x0, x1, y0, y1, m, l1, l2, l3

# 肌の色（箱の中の明るい画素の中央値）と、髪の色（渡されなければ暗い画素の中央値）
allc = []
for t, uv, V in tris:
    r = pixels_of(uv)
    if r is None: continue
    x0, x1, y0, y1, m, *_ = r
    allc.append(orig[y0:y1 + 1, x0:x1 + 1, :3][m])
allc = np.concatenate(allc)
lum = allc.mean(1)
skin = np.median(allc[lum > np.percentile(lum, 50)], 0)
if HAIR is None: HAIR = np.median(allc[lum < np.percentile(lum, 10)], 0)
def redness(c): return c[..., 0] - (c[..., 1] + c[..., 2]) / 2
skin_red = redness(skin)
print("SC 三角形 %d  肌の色 %s  髪の色 %s" % (len(tris), np.round(skin * 255).astype(int), np.round(HAIR * 255).astype(int)))

# どの面も使っていない画素（島の外）の地図。
# 肌の三角形の辺のすぐ外に、どの面も使っていない灰色の画素が残っていて、描くときに辺ににじみ、目の高さに細い線が出た。
# texpad.py はその画素を「いちばん近い島の色」で埋めるが、髪の島が近いと灰色になった。
# 肌にした三角形の辺の外 EXT 画素までの、どの面も使っていない画素も肌の色で埋める
EXT = 3.0
used = np.zeros((H, W), bool)
for t in em.loop_triangles:
    uv = np.array([uvl[li].uv for li in t.loops], dtype=np.float64)
    r = pixels_of(uv)
    if r is None: continue
    x0, x1, y0, y1, m, *_ = r
    used[y0:y1 + 1, x0:x1 + 1] |= m
print("SC 面が使っている画素 %d / %d" % (int(used.sum()), W * H))

# 顔の面（前後 y を x,z の3次式で表す）を、肌が多い三角形の頂点から当てる（外れた点は除いて当て直す）
def Bs(x, z): return np.stack([x ** i * z ** j for i in range(4) for j in range(4 - i)], 1)
surf = None
if INNER is not None:
    pts = []
    for t, uv, V in tris:
        r = pixels_of(uv)
        if r is None: continue
        x0, x1, y0, y1, m, *_ = r
        blk = orig[y0:y1 + 1, x0:x1 + 1, :3]
        hp = m & (np.linalg.norm(blk - HAIR, axis=2) < np.linalg.norm(blk - skin, axis=2))
        if hp.sum() < 0.2 * max(m.sum(), 1): pts.append(V)
    Q = np.concatenate(pts); kq = np.ones(len(Q), bool)
    for it in range(4):
        cs, *_ = np.linalg.lstsq(Bs(Q[kq, 0], Q[kq, 2]), Q[kq, 1], rcond=None)
        rq = Q[:, 1] - Bs(Q[:, 0], Q[:, 2]) @ cs; sq = np.std(rq[kq]); kq = np.abs(rq) < 2 * sq
    surf = cs
    print("SC 顔の面を当てた（点 %d、ばらつき %.4f）" % (int(kq.sum()), sq))

done = 0; wx = 0.2 * (X1 - X0); wz = 0.2 * (Z1 - Z0)
painted = np.zeros((H, W), bool)          # 画素は1回だけ塗る（三角形の縁の画素が重なるため）
for t, uv, V in tris:
    r = pixels_of(uv, EXT)
    if r is None: continue
    x0, x1, y0, y1, m, l1, l2, l3, mx = r
    blk = orig[y0:y1 + 1, x0:x1 + 1, :3]
    on_face = False
    if surf is not None:
        c = V.mean(0)
        if INNER[0] <= c[0] <= INNER[1] and INNER[2] <= c[2] <= INNER[3]:
            # 顔の面から 4mm 以内なら肌（手前がマイナス。前髪は面より手前に浮いている）
            dy = c[1] - (Bs(np.array([c[0]]), np.array([c[2]])) @ surf)[0]
            on_face = dy > -0.004
    # 肌の三角形なら、辺の外のどの面も使っていない画素も対象に含める（髪の三角形では広げない）
    hp = m & (np.linalg.norm(blk - HAIR, axis=2) < np.linalg.norm(blk - skin, axis=2))
    if on_face or hp.sum() < 0.5 * max(m.sum(), 1):
        m = m | (mx & ~used[y0:y1 + 1, x0:x1 + 1])
    dh = np.linalg.norm(blk - HAIR, axis=2); ds = np.linalg.norm(blk - skin, axis=2)
    hairpx = m & (dh < ds)
    keep_hair = hairpx if hairpx.sum() >= 0.5 * max(m.sum(), 1) else np.zeros_like(m)
    if on_face: keep_hair = np.zeros_like(m)
    # 赤みは、肌より赤い分に応じてなだらかに残す（0/1 で分けたら頬の赤みのふちがくっきりした）
    kr = np.clip((redness(blk) - skin_red) / (2 * RED), 0, 1)[..., None]
    red = m & (kr[..., 0] >= 1.0)
    change = m & ~keep_hair & ~red & ~painted[y0:y1 + 1, x0:x1 + 1]
    if not change.any(): continue
    # 画素ごとの 3D 位置 → 箱のふちで弱める
    Xp = l1 * V[0, 0] + l2 * V[1, 0] + l3 * V[2, 0]
    Zp = l1 * V[0, 2] + l2 * V[1, 2] + l3 * V[2, 2]
    fx = np.clip(np.minimum(Xp - X0, X1 - Xp) / wx, 0, 1); fz = np.clip(np.minimum(Zp - Z0, Z1 - Zp) / wz, 0, 1)
    f = (fx * fz)[..., None]; f = f * f * (3 - 2 * f)
    out = px[y0:y1 + 1, x0:x1 + 1, :3]
    f = f * (1 - kr)
    new = blk * (1 - f) + skin * f
    out[change] = new[change]
    px[y0:y1 + 1, x0:x1 + 1, :3] = out
    painted[y0:y1 + 1, x0:x1 + 1] |= change
    done += int(change.sum())
print("SC 肌の色にした画素 %d" % done)
o = bpy.data.images.new("o", W, H); o.pixels = px.ravel().tolist()
o.filepath_raw = OUT; o.file_format = 'PNG'; o.save(); print("SC 書き出し", OUT)
