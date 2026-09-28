# -*- coding: utf-8 -*-
"""別のキャラの顔へ、手本のキャラ（v55）の顔の「絵」を写す。

   手本と写す先は、頭の形も大きさも違う。だから位置をそのまま合わせる mouth3d.py は使えない。
   代わりに、正面から見た左目・右目・口の中心（world の x, z）を両方で測っておき、
   その3点が重なるように、写す先の顔の点を手本の顔の点へ変換する（2次元のアフィン変換）。
   変換した点から手本の顔へ正面から光線を当て、当たった面のUVで手本のテクスチャの色を拾う。

   テクスチャは面ごとに散らばっているので、写す先も mouthpaste.py と同じく
   顔の正面の三角形をひとつずつテクスチャの画素に展開し、画素ごとに位置を求めて塗る。

   塗る範囲と、塗らない画素:
   - 範囲は目と口を囲む楕円。ふちはぼかして、元の肌へなじませる。
   - 目と口のまわり（小さい楕円の中）は、手本の絵をそのまま入れる。
     ただし写す先の赤いメガネの線は残す（秀才少女のメガネは絵で描いてあるため）。
   - それ以外（頬・おでこ・あご）は、写す先が肌色の画素だけ塗る。前髪・眉・襟は残る。
     手本の側が髪の色の画素（前髪が顔に掛かっている所）も塗らない。写す先の肌が残る。
   - 肌の色味は、両方の頬の色の中央値の比で手本の色を寄せる。

   実行: blender -b --factory-startup -P facecopy.py --
         手本.glb 写す先.glb 出力テクスチャ.png 出力.glb
         手本の点 "左目x,z;右目x,z;口x,z" 写す先の点 "左目x,z;右目x,z;口x,z"
         [メガネを残す 1/0 既定1] [前の限界y 既定-0.05] [骨を素の姿勢に戻す 1/0 既定0]
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, OUTPNG, OUTGLB = a[0], a[1], a[2], a[3]
def pts(s): return np.array([[float(v) for v in p.split(',')] for p in s.split(';')])
SP, DP = pts(a[4]), pts(a[5])
KEEPGLASS = (a[6] != '0') if len(a) > 6 and a[6] else True
YCUT = float(a[7]) if len(a) > 7 and a[7] else -0.05
# 1 なら骨の姿勢を完全に素（バインド姿勢）へ戻してから測る。
# アニメを外しても骨に姿勢が残り、アニメを移したモデルでは頭が横を向いたままになる。
# 目・口の位置もこの姿勢で測ったものを渡すこと
RESETPOSE = len(a) > 8 and a[8] == '1'
# 1 なら「目と口だけ切り出して貼る」。肌は写す先のものを残し、手本からは肌と違う色の画素
# （まつ毛・白目・瞳・口・鼻の点）だけを、肌の色から離れているほど濃く重ねる。
# 顔全体を写すと、手本の肌と写す先の肌が混ざって、水彩のしみのような肌荒れに見えた（のっぺらぼうから作ったお嬢様）
FEATONLY = len(a) > 9 and a[9] == '1'
# 手本の鼻の点（world の x,z）。目と口だけ貼るときに、鼻の点もいっしょに貼る
SNOSE = np.array([float(v) for v in a[10].split(',')]) if len(a) > 10 and a[10] else None

def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    if arm and arm.animation_data: arm.animation_data.action = None
    if arm and RESETPOSE:
        from mathutils import Matrix
        for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    me = next(o for o in bpy.data.objects if o.type == 'MESH')
    img = None
    for m in me.data.materials:
        if not m or not m.use_nodes: continue
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
    mesh = me.data
    mesh.calc_loop_triangles()
    MW = me.matrix_world
    # 骨で変形したあとの位置を使う。アニメを外しても骨には姿勢が残っていて、
    # 変形前の座標とは頭で 7〜10cm ずれる。目と口の位置は描いた絵（変形後）で測っているので、そちらに揃える
    dg = bpy.context.evaluated_depsgraph_get(); oe = me.evaluated_get(dg); em = oe.to_mesh()
    P = np.array([tuple(MW @ v.co) for v in em.vertices], dtype=np.float64)
    oe.to_mesh_clear()
    uv = np.array([tuple(l.uv) for l in mesh.uv_layers.active.data], dtype=np.float64)
    TL = np.array([tuple(t.loops) for t in mesh.loop_triangles], dtype=np.int64)
    TV = np.array([tuple(t.vertices) for t in mesh.loop_triangles], dtype=np.int64)
    W, H = img.size
    A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)   # 下の行が先頭
    return me, mesh, img, P, uv, TL, TV, A, W, H

def hsv(c):
    c = np.atleast_2d(c)
    mx = c.max(1); mn = c.min(1); d = np.maximum(mx-mn, 1e-6)
    r, g, b = c[:, 0], c[:, 1], c[:, 2]
    h = np.where(mx == r, ((g-b)/d) % 6, np.where(mx == g, (b-r)/d + 2, (r-g)/d + 4)) / 6.0
    s = np.where(mx > 0, (mx-mn)/np.maximum(mx, 1e-6), 0)
    return h, s, mx

# ---- 手本 ----
_, _, _, SPv, Suv, STL, STV, SA, SW, SH = load(SRC)
bvh = BVHTree.FromPolygons([Vector(p) for p in SPv], [tuple(t) for t in STV])
print("FC 手本 三角形 %d  テクスチャ %dx%d" % (len(STV), SW, SH))

# ---- 写す先 ----
me, mesh, img, P, uv, TL, TV, A, W, H = load(DST)
print("FC 写す先 三角形 %d  テクスチャ %dx%d" % (len(TV), W, H))

# 写す先の (x,z) → 手本の (x,z)。3点からアフィン変換を解く
M = np.linalg.solve(np.hstack([DP, np.ones((3, 1))]), SP)          # 3x2
def to_src(xz): return np.hstack([xz, np.ones((len(xz), 1))]) @ M

# 写す先の顔の枠: 目の軸を u、そこから口へ向かう向きを v。目の間隔で割る
eL, eR, mo = DP
mid = (eL + eR) / 2; ex = eR - eL; sp = np.linalg.norm(ex); ex /= sp
ey = np.array([ex[1], -ex[0]])
if np.dot(mo - mid, ey) < 0: ey = -ey
def frame(xz):
    d = xz - mid
    return d @ ex / sp, d @ ey / sp
mu, mv = frame(mo[None])
mu, mv = float(mu[0]), float(mv[0])
print("FC 写す先 目の間隔 %.3f m  口の位置 u %.2f v %.2f" % (sp, mu, mv))
# 塗る範囲の楕円。上は眉の少し上（v -0.6）、下は口の少し下まで。
# 下を広く取ると、あごの裏から首へ回り込み、手本の首の影や紐の色を拾って茶色い筋になった
RU = 0.95
VTOP, VBOT = -0.6, mv + 0.25
VC, RV = (VTOP + VBOT) / 2, (VBOT - VTOP) / 2
def region(u_, v_): return np.sqrt((u_/RU)**2 + ((v_-VC)/RV)**2)

# 顔の正面の三角形
cands = []
for t in range(len(TV)):
    Q = P[TV[t]]
    if Q[:, 1].max() > YCUT: continue
    n = np.cross(Q[1]-Q[0], Q[2]-Q[0])
    nl = np.linalg.norm(n)
    if nl < 1e-12 or n[1] >= 0: continue
    u_, v_ = frame(Q[:, [0, 2]])
    if np.all(region(u_, v_) > 1.0): continue
    # あごの裏など、下を向いた面は塗らない。
    # ただし口のまわりは別。彫り込まれた口の天井も下を向いていて、そこを外すと元の口の赤が残って欠けて見えた
    inMouth = np.any(((u_-mu)/0.40)**2 + ((v_-mv)/0.30)**2 < 1.0)
    if n[2] / nl < -0.5 and not inMouth: continue
    cands.append(t)
print("FC 対象の三角形 %d" % len(cands))

def tri_pixels(uvt, tolpx):
    """UV三角形の中の画素と重心座標。tolpx 画素ぶん、ふちの外まで含める"""
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
    # 重心座標は「辺までの距離 ÷ 高さ」なので、辺ごとに高さで割って画素に換算する
    area2 = abs(det)
    def hgt(p, q): return area2 / max(np.hypot(q[0]-p[0], q[1]-p[1]), 1e-9)
    h1, h2, h3 = hgt(px[1], px[2]), hgt(px[2], px[0]), hgt(px[0], px[1])
    ok = (l1 >= -tolpx/h1 - 1e-6) & (l2 >= -tolpx/h2 - 1e-6) & (l3 >= -tolpx/h3 - 1e-6)
    return ys.ravel()[ok], xs.ravel()[ok], np.stack([l1[ok], l2[ok], l3[ok]], 1)

# どれかの三角形に属する画素の地図。ふちの外を塗るのは、どの三角形にも属さない隙間の画素だけ。
# ふちを塗り残すと、描くときに補間で元の色が混ざり、舌や瞳に細いひびの線が出た
owned = np.zeros((H, W), dtype=bool)
for t in range(len(TV)):
    r = tri_pixels(uv[TL[t]], 0.0)
    if r is not None: owned[r[0], r[1]] = True

def sample_src(x, z, front_only):
    loc, nrm, fi, dist = bvh.ray_cast(Vector((x, -5.0, z)), Vector((0, 1, 0)), 10.0)
    if loc is None: return None
    if front_only and nrm.y > -0.2: return None   # 手本の側で横や下を向いた面（引き伸ばされた絵）は使わない
    tv = STV[fi]; Q = SPv[tv]
    # 当たった点の重心座標
    v0, v1 = Q[1]-Q[0], Q[2]-Q[0]; v2 = np.array(loc) - Q[0]
    d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1; d20, d21 = v2 @ v0, v2 @ v1
    den = d00*d11 - d01*d01
    if abs(den) < 1e-14: return None
    b1 = (d11*d20 - d01*d21) / den; b2 = (d00*d21 - d01*d20) / den; b0 = 1 - b1 - b2
    u = Suv[STL[fi]]
    uvp = b0*u[0] + b1*u[1] + b2*u[2]
    ix = min(SW-1, max(0, int(uvp[0]*SW))); iy = min(SH-1, max(0, int(uvp[1]*SH)))
    return SA[iy, ix, :3]

# 画素ごとに: 写す先の位置 → 重み・種類を決め、手本の色を拾う
done = np.zeros((H, W), dtype=bool)
rec_y, rec_x, rec_c, rec_w, rec_skin, rec_feat = [], [], [], [], [], []
if SNOSE is not None:
    # 手本の鼻の点を写す先の枠へ戻す（写す先 → 手本の変換の逆）
    Minv = np.linalg.solve(np.hstack([SP, np.ones((3, 1))]), DP)
    dn = np.array([SNOSE[0], SNOSE[1], 1.0]) @ Minv
    nu, nv_ = [float(t[0]) for t in frame(dn[None])]
    print("FC 鼻の点 写す先 x %.4f z %.4f（u %.2f v %.2f）" % (dn[0], dn[1], nu, nv_))
for tolpx in (0.0, 2.0):
    for t in cands:
        r = tri_pixels(uv[TL[t]], tolpx)
        if r is None: continue
        ys, xs, L = r
        sel = ~done[ys, xs]
        if tolpx > 0: sel &= ~owned[ys, xs]
        ys, xs, L = ys[sel], xs[sel], L[sel]
        if not len(ys): continue
        wp = L @ P[TV[t]]
        xz = wp[:, [0, 2]]
        u_, v_ = frame(xz)
        rr = region(u_, v_)
        w = np.clip((1.0 - rr) / 0.18, 0, 1)
        # 目の楕円は、まつ毛の先まで入る大きさ。狭いと手本と写す先のまつ毛が二重に残った
        inE = (((np.abs(u_)-0.5)/0.56)**2 + (v_/0.42)**2) < 1.0
        inM = (((u_-mu)/0.40)**2 + ((v_-mv)/0.30)**2) < 1.0
        th, ts, tvv = hsv(A[ys, xs, :3])
        tskin = (((th > 0.92) | (th < 0.12)) & (ts > 0.04) & (ts < 0.5) & (tvv > 0.55))
        glass = ((th > 0.93) | (th < 0.04)) & (ts > 0.45) & (tvv > 0.45) & (v_ < mv - 0.15)
        sxz = to_src(xz)
        inN = ((((u_-nu)/0.12)**2 + ((v_-nv_)/0.10)**2) < 1.0) if SNOSE is not None else np.zeros(len(ys), bool)
        for k in range(len(ys)):
            if w[k] <= 0 and not FEATONLY: continue
            feat = inE[k] or inM[k] or inN[k]
            if FEATONLY and not feat: continue
            if KEEPGLASS and glass[k]: continue
            if not feat and not tskin[k]: continue
            c = sample_src(sxz[k, 0], sxz[k, 1], not feat)
            if c is None: continue
            # 目と口だけ貼るときは、瞳の円（目の中心から半径 0.24）の外なら目の楕円のどこでも髪色を外す。
            # 「上 -0.28 より上か、横 0.8 より外」の区切りでは、右目の外の角（横 0.73・上 -0.26）にオレンジの切れ端が残った
            outIris = inE[k] and (((abs(u_[k]) - 0.5)**2 + (v_[k] - 0.02)**2) > 0.24**2)
            if feat and ((v_[k] < -0.28 or abs(u_[k]) > 0.8) or (FEATONLY and outIris)):
                # 目の楕円の上側（まつ毛より上）と外側（こめかみ）に掛かった手本の眉・前髪・横髪の髪色は写さない。
                # 瞳も茶色で色が近いので、瞳のある所（v -0.28 より下で、目の中心から横 0.3 以内）には掛けない
                sh_, ss_, sv_ = hsv(c)
                # 目と口だけ貼るときは、髪と肌が混ざった薄い茶色（鮮やかさ 0.25〜0.45）も外す。
                # 肌は写す先のものが残るので外しても穴にならず、外さないと目尻の上に茶色いしみが残った
                # 暗めのオレンジ（明るさ 0.45 未満）の切れ端も右目の外に残ったので、明るさの条件も下げる。
                # まつ毛は灰色に近く鮮やかさが低いので、この条件では外れない
                if (0.03 < sh_[0] < 0.13) and ss_[0] > (0.25 if FEATONLY else 0.45) and sv_[0] > (0.2 if FEATONLY else 0.45): continue
            if not feat:
                # 手本の側も肌の画素だけ使う。前髪・眉・横髪のふち（髪と肌が混ざった画素）は外す。
                # 髪のふちは鮮やかさが肌に近いので、色相（肌 0.047、髪 0.075 前後）で分ける
                sh_, ss_, sv_ = hsv(c)
                if not (((sh_[0] > 0.90) or (sh_[0] < 0.062)) and 0.04 < ss_[0] < 0.5 and sv_[0] > 0.55): continue
            done[ys[k], xs[k]] = True
            rec_y.append(ys[k]); rec_x.append(xs[k]); rec_c.append(c); rec_w.append(1.0 if feat else w[k])
            rec_skin.append((not feat) and tskin[k] and (abs(u_[k]) < 0.9) and (0.15 < v_[k] < mv))
            rec_feat.append(feat)

ry, rx = np.array(rec_y), np.array(rec_x)
rc, rw, rs = np.array(rec_c), np.array(rec_w), np.array(rec_skin)
print("FC 塗る画素 %d（うち肌 %d）" % (len(ry), rs.sum()))
if FEATONLY:
    # 手本の肌の色（貼る範囲の中の肌らしい画素の中央値）から離れている画素ほど濃く重ねる。
    # 肌そのものは透明になり、写す先の肌が残る
    sh_, ss_, sv_ = hsv(rc)
    sk = ((sh_ > 0.90) | (sh_ < 0.062)) & (ss_ > 0.04) & (ss_ < 0.5) & (sv_ > 0.55)
    smed = np.median(rc[sk], 0)
    dist = np.linalg.norm(rc - smed, axis=1)
    rw = np.clip((dist - 0.05) / 0.10, 0, 1)
    print("FC 目と口だけ: 手本の肌 %s  重ねる画素 %d（半分以上の濃さ %d）" % (np.round(smed, 3), int((rw > 0).sum()), int((rw > 0.5).sum())))
    rs = np.zeros(len(ry), bool)        # 肌の色合わせはしない（肌は写す先のまま）
# 肌の色味合わせ
if rs.sum() > 50:
    src_med = np.median(rc[rs], 0); dst_med = np.median(A[ry[rs], rx[rs], :3], 0)
    gain = np.clip(dst_med / np.maximum(src_med, 1e-4), 0.85, 1.15)
    print("FC 肌の中央値 手本 %s 写す先 %s 倍率 %s" % (np.round(src_med, 3), np.round(dst_med, 3), np.round(gain, 3)))
    # 倍率は手本の肌の画素だけに掛ける。白目や口にまで掛けると、白目が水色がかった
    sh_, ss_, sv_ = hsv(rc)
    sk = (((sh_ > 0.90) | (sh_ < 0.062)) & (ss_ > 0.04) & (ss_ < 0.5) & (sv_ > 0.55)).astype(np.float32)[:, None]
    rc = np.clip(rc * (1 + (gain - 1) * sk), 0, 1)
A[ry, rx, :3] = A[ry, rx, :3] * (1 - rw[:, None]) + rc * rw[:, None]

img.pixels = A.ravel().tolist()
img.filepath_raw = OUTPNG; img.file_format = 'PNG'; img.save()
print("FC テクスチャ", OUTPNG)
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
print("FC 書き出し", OUTGLB, os.path.getsize(OUTGLB))
