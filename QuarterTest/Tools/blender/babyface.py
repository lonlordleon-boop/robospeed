# -*- coding: utf-8 -*-
"""乳児期の赤ちゃん（顔を描き込んだ三面図から生成）の顔を整える（2026年9月23日）。

   「顔が薄っぺらく見える・肌が汚い・ひびが入っている」と言われて調べた:
   ・生成のメッシュは絵の継ぎ目（UV の切れ目）で頂点が分かれていて、分かれた頂点どうしで法線が違う。
     光を当てると、継ぎ目と大きな三角形の境目がひびのような線とまだらに見えた
   ・目・口・鼻が彫り込まれていて、その縁に段がある。右目の下にはへこみもある

   やること:
   1. 読み込んだ法線を捨て、同じ位置の頂点を溶接して、なめらかな面にする（UV は面の角ごとに残るので、絵はずれない）
   2. 顔の前面の網目を細かくする（辺を2等分。UV も一緒に割るので絵はずれない）
   3. 顔になめらかな曲面（前後 y を 左右 x・高さ z の3次式で表す）を当てはめ、頂点を前後（y）だけその曲面へ寄せる。
      正面から見た位置は動かないので、描いた目・口は崩れない。彫られた目・口のくぼみの点は外して当て直す。
      寄せる強さは箱のふちで 0 へ段々に落とす。あごの下は箱の外。鼻のまわりは寄せない
   試してやめた寄せ方（同じ日）:
   ・Smooth を3方向に掛ける: 頂点が面に沿って滑り、描いた目の絵が引きずられて崩れた
   ・その動きを面に垂直な分だけ残す: 目のくぼみの縁で向きがばらばらなので、しわが寄った
   ・前後だけ Smooth: くぼみの壁（ほぼ前後向き）どうしが平均されて、しわが寄った。網目を細かくすると余計に寄った
   ・ラプラス平滑化の「体積を保つ」: 全体をずらして帳尻を合わせるので、体じゅうの頂点が動いた
   試したがやめた方法:
   ・facefit.py（曲面へ寄せる）: 前を向いた頂点だけ動かすので、あごの下で前と下の面が裂けて黒い線が出た。鼻も消えた
   ・skinnormal.py（法線だけならす）: 正面から見た平面で平均するので、あごの下や口の中の法線まで混ざり、頬の下に黒いしみが出た

   座標は Blender（x 左右・y 前が −・z 上、床 z=0）。baby_norm.glb を入れる。
   実行: blender -b --factory-startup -P babyface.py -- 入力.glb 出力.glb
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(a[0]), os.path.abspath(a[1])
def log(s): print("[face] " + str(s))

# 顔の前面の箱（下からの眺めと横の方眼で測った。前髪は 1.19 より上、横の髪は左右 0.36 より外、フードのふちは前後 -0.62 より奥）
BOX = dict(x=(-0.36, 0.36), z=(0.76, 1.19), y=(-1.0, -0.62))   # 下の 0.76 はあごの下の曲がり始めより上（下まで入れると、あごの下で前と下の面が裂けた）
FALL = 0.06            # ふちでならす強さを 0 へ落とす幅
NOSE = (Vector((0.0, -0.905, 0.975)), 0.045, 0.03)   # 鼻の中心・守る半径・ぼかし幅（方眼の横と正面で測った）

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
me = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
bpy.ops.object.select_all(action='DESELECT'); me.select_set(True); bpy.context.view_layer.objects.active = me
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
try:
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
except Exception as e:
    log("読み込んだ法線は無かった: %s" % e)
n0 = len(me.data.vertices)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=1e-4)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.shade_smooth()
log("溶接: 頂点 %d → %d" % (n0, len(me.data.vertices)))

# ならす強さ（頂点グループ）
def ramp(v, lo, hi):
    t = min(v - lo, hi - v) / FALL
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)

# 顔の網目を細かくする。顔は 650 頂点の大きな三角形でできていて、ならしても三角形の大きさのまだらが残った。
# 箱の中の面だけ、辺を CUTS+1 等分する（UV も一緒に割るので絵はずれない）
CUTS = 1
bm = bmesh.new(); bm.from_mesh(me.data)
def inbox(co): return BOX['x'][0] - 0.02 < co.x < BOX['x'][1] + 0.02 and BOX['z'][0] - 0.02 < co.z < BOX['z'][1] + 0.02 and co.y < BOX['y'][1] + 0.02
fs = [f for f in bm.faces if all(inbox(v.co) for v in f.verts)]
es = list({e for f in fs for e in f.edges})
nv0 = len(bm.verts)
bmesh.ops.subdivide_edges(bm, edges=es, cuts=CUTS, use_grid_fill=True)
bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
bm.to_mesh(me.data); bm.free(); me.data.update()
for pg in me.data.polygons: pg.use_smooth = True
log("顔の網目を細かくした: 面 %d 枚 → 頂点 %d → %d" % (len(fs), nv0, len(me.data.vertices)))
vg = me.vertex_groups.new(name='face_smooth')
P0 = np.array([tuple(v.co) for v in me.data.vertices])
N0 = np.array([tuple(v.normal) for v in me.data.vertices])
n = 0
for v in me.data.vertices:
    p = v.co
    w = ramp(p.x, *BOX['x']) * ramp(p.z, *BOX['z']) * ramp(p.y, *BOX['y'])
    if w > 1e-4:
        vg.add([v.index], w, 'REPLACE'); n += 1
log("ならす頂点: %d" % n)

W = np.zeros(len(me.data.vertices))
for v in me.data.vertices:
    for g in v.groups:
        if g.group == vg.index: W[v.index] = g.weight
def basis(x, z, order=3):
    return np.stack([x ** i * z ** j for i in range(order + 1) for j in range(order + 1 - i)], 1)
m = W > 0.5
X, Z, Y = P0[m, 0], P0[m, 2], P0[m, 1]
keep = np.ones(len(X), bool)
for it in range(3):                                 # くぼみ（奥 = y が大きい）と出っぱりを外して当て直す
    c, *_ = np.linalg.lstsq(basis(X[keep], Z[keep]), Y[keep], rcond=None)
    r = Y - basis(X, Z) @ c; sd = r[keep].std()
    keep = (r < 1.2 * sd) & (r > -2.0 * sd)
    log("当てはめ %d: 使った点 %d / %d・ずれの幅 %.4f" % (it + 1, keep.sum(), len(X), sd))
fit = basis(P0[:, 0], P0[:, 2]) @ c
# 鼻は形を保ったまま、まわりの面と同じだけ前後に動かす（鼻だけ動かさないと、鼻のまわりに段ができた）
dn = np.linalg.norm(P0 - np.array(NOSE[0]), axis=1)
ns = np.clip((dn - NOSE[1]) / NOSE[2], 0, 1)          # 鼻 0 … まわり 1
ring = (dn > NOSE[1]) & (dn < NOSE[1] + NOSE[2] + 0.02) & (W > 0.5)
dnose = float(np.median((fit - P0[:, 1])[ring])) if ring.any() else 0.0
log("鼻を動かす量: %.4f（まわり %d 点）" % (dnose, ring.sum()))
P1 = P0.copy(); P1[:, 1] = P0[:, 1] + W * (ns * (fit - P0[:, 1]) + (1 - ns) * dnose)
for v, q in zip(me.data.vertices, P1): v.co = Vector(tuple(q))
me.data.update()
# 彫られたくぼみの壁は、曲面へ寄せると押しつぶされて、後ろ向きか面積のない面になる。そこだけ黒い切れ込みに見えたので消す
bm = bmesh.new(); bm.from_mesh(me.data); bm.verts.ensure_lookup_table(); bm.normal_update()
nose_r = NOSE[1] + NOSE[2]                           # 鼻の裏（下向きの面）は本物なので消さない（はじめ消して、鼻の下に穴が開いた）
dead = [f for f in bm.faces if all(W[v.index] > 0.3 for v in f.verts) and (f.normal.y > -0.3 or f.calc_area() < 1e-7)
        and min((v.co - NOSE[0]).length for v in f.verts) > nose_r]
bmesh.ops.delete(bm, geom=dead, context='FACES')
bm.to_mesh(me.data); bm.free(); me.data.update()
log("消した面（押しつぶされたくぼみの壁）: %d" % len(dead))
# （このあと前後だけ Smooth を6回掛けてみたが、また しわ と右目の横の黒い筋が出たのでやめた）
P1 = np.array([tuple(v.co) for v in me.data.vertices]); P0 = P0[:len(P1)]
d = np.linalg.norm(P1 - P0, axis=1)
log("動いた量: 平均 %.4f / 最大 %.4f（動いた頂点 %d）" % (d[d > 1e-5].mean() if (d > 1e-5).any() else 0, d.max(), int((d > 1e-5).sum())))
if 'face_smooth' in me.vertex_groups: me.vertex_groups.remove(me.vertex_groups['face_smooth'])

bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_yup=True, export_image_format='AUTO')
log("書き出し: %s" % OUT)
