# -*- coding: utf-8 -*-
"""服に隠れる素体の面を、服の内側へ引っ込める「モーフ（形状キー）」を素体に作る。

   素体の面と服の面がほぼ同じ深さに並ぶと、描画がどちらを手前と見るか毎コマ揺れて、
   服が透けたように見える。穴が開いているのではなく、深さの取り合い。
   だから素体と服のあいだに必ずすき間を作れば、原理的に起きなくなる。

   服を大きくして逃げる手もあるが、服がぼてっとして三面図の形から離れる。
   素体を消す手もあるが、動いたときに消した所が出てきて穴になる。
   引っ込めるだけなら、形は保ったまま、脱げば元に戻せる。

   服は単体で作った閉じた殻なので、内外の判定が正しくできる。
   （灰色マネキンから切り出した服は開いた膜なので、これができなかった）

   判定は、素体の頂点からその面の向き（外向き）へ光線を飛ばすだけ。
   外向きに服が当たれば、その頂点はもう服の内側にいる。当たった距離がすき間より近いときだけ、
   その分を内へ下げる。外向きに当たらず、内向きに当たったときは、服を突き抜けて外に出ている。
   当たった距離＋すき間だけ内へ下げる。どちらにも当たらなければ服の外（袖から出た腕、裾から出た脚）
   なので触らない。

   一番近い面を探す方法は使わない。服が体より大きいとき、離れた所の面をつかんで、
   素体を外向きに何センチも動かしてしまった。

   結果は形状キーとして書き込むので、素体そのものの形は変わらない。
   dressup.html と Unity では、服を着せたときだけこのキーを1にする。

   実行: blender -b --factory-startup -P sinkbody.py -- 入力.glb 出力.glb 部品の種類 [すき間 m 既定0.004] [動かす上限 m 既定0.03]
   例:   ... -- doll.glb doll_s.glb cloth 0.004 0.03
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, KIND = a[0], a[1], a[2]
GAP = float(a[3]) if len(a) > 3 else 0.004    # 服の面から素体をどれだけ内側に置くか
MAXM = float(a[4]) if len(a) > 4 else 0.03    # 1頂点を動かす上限。これを超えると体の形が崩れる
# 服の縁の際で光線が外れた頂点を救うための、ごく短い探し半径。大きくすると離れた面をつかんで崩れる
EDGE = float(a[5]) if len(a) > 5 else 0.010
# 縫い目の際で判定から漏れた下着を、まとめて引っ込める深さ（m）
UW = float(a[6]) if len(a) > 6 else 0.008

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
body = next((o for o in meshes if o.name == 'body'), None) or meshes[0]

def kind_of(o):
    for m in o.data.materials:
        if m and ':' in m.name: return m.name.split(':')[0]
    return ''

part = next((o for o in meshes if o is not body and kind_of(o) == KIND), None)
if part is None:
    print("SB 種類 %s の部品が見つからない。あるのは %s" % (KIND, [(o.name, kind_of(o)) for o in meshes]))
    sys.exit(1)
print("SB 素体 %s（頂点 %d）  部品 %s（頂点 %d）" % (body.name, len(body.data.vertices), part.name, len(part.data.vertices)))

# 部品を world 座標の木にする
pm = part.data
verts = [part.matrix_world @ v.co for v in pm.vertices]
polys = [list(p.vertices) for p in pm.polygons]
bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)

# 素体の「下着」の面を、テクスチャの色で拾う。白っぽい（鮮やかさが低く明るい）面。
# 下着は服の下にしか無いので、まとめて少し引っ込めても外からは分からない。
# 光線の判定は、服の縁の際で面が斜めを向いていると外れる。股の縫い目がちょうどそれで、
# 下着が数十枚だけ白いトゲとして飛び出して「股に穴が開いている」ように見えていた。
import colorsys
underwear = set()
img = None
for m in body.data.materials:
    if not m or not m.node_tree: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
if img is not None and body.data.uv_layers.active:
    W, H = img.size
    A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    uvl = body.data.uv_layers.active.data
    for f in body.data.polygons:
        uv = [uvl[li].uv for li in f.loop_indices]
        cx = sum(u.x for u in uv)/len(uv); cy = sum(u.y for u in uv)/len(uv)
        c = A[min(H-1, int(cy*H)), min(W-1, int(cx*W)), :3]
        h_, s_, v_ = colorsys.rgb_to_hsv(float(c[0]), float(c[1]), float(c[2]))
        if s_ < 0.12 and v_ > 0.55:
            for vi in f.vertices: underwear.add(vi)
print("SB 下着とみなした頂点 %d（テクスチャが白っぽい面）" % len(underwear))

MW = body.matrix_world
MWI = MW.inverted()
NM = MW.to_3x3()
moved = 0; total = 0.0; mx = 0.0; capped = 0; outside = 0; edge = 0; uw = 0
new = []
for v in body.data.vertices:
    p = MW @ v.co
    n = (NM @ v.normal).normalized()
    out = bvh.ray_cast(p + n * 1e-4, n, MAXM + GAP)      # 外向きに服があるか
    if out[0] is not None:
        t = out[3]
        if t >= GAP: new.append(v.co.copy()); continue   # すでに十分内側
        d = GAP - t                                      # 足りないぶんだけ下げる
    else:
        inn = bvh.ray_cast(p - n * 1e-4, -n, MAXM)       # 内向きに服があるか
        if inn[0] is None:
            # 光線がどちらにも当たらない。ふつうは服の外（袖から出た腕、裾から出た脚）。
            # ただし縫い目の際は面が斜めを向いていて、両方の光線が外れる。
            # 股の縫い目がちょうどそれで、下着が白いトゲとして飛び出していた。
            # ごく近く（EDGE）に服の面があるときだけ、その面の内側へ置き直す。
            # 法線方向へ下げるのではなく面の内側へ置くので、体に引きつれた筋が出ない。
            # 探す半径を小さく抑えるのが肝心。半径なしで一番近い面を探すと、
            # 服が体より大きいとき離れた面をつかんで素体を外へ何センチも動かした。
            near = bvh.find_nearest(p, EDGE)
            if near[0] is None:
                outside += 1; new.append(v.co.copy()); continue
            loc, nor = near[0], near[1]
            if (p - loc).dot(nor) < -GAP:
                new.append(v.co.copy()); continue        # すでに十分内側
            q = loc - nor * GAP
            if (q - p).length > MAXM:
                outside += 1; new.append(v.co.copy()); continue
            new.append(MWI @ q); edge += 1
            moved += 1; total += (q - p).length; mx = max(mx, (q - p).length)
            continue
        d = inn[3] + GAP                                 # 突き抜けているぶん＋すき間
    if d > MAXM: d = MAXM; capped += 1
    q = p - n * d
    new.append(MWI @ q)
    moved += 1; total += d; mx = max(mx, d)
print("SB 引っ込めた頂点 %d / %d（平均 %.1f mm、最大 %.1f mm、上限に当たった %d）"
      % (moved, len(body.data.vertices), (total/moved*1000 if moved else 0), mx*1000, capped))
print("SB 服の外にいて触らなかった頂点 %d、縁の際で救った頂点 %d、下着として引っ込めた頂点 %d" % (outside, edge, uw))
if not moved:
    print("SB 動かす頂点が無かった"); sys.exit(1)

# 形状キーにする。素体そのものの形は変えない
if body.data.shape_keys is None:
    body.shape_key_add(name='Basis', from_mix=False)
name = 'sink_' + KIND
old = body.data.shape_keys.key_blocks.get(name)
if old: body.shape_key_remove(old)
sk = body.shape_key_add(name=name, from_mix=False)
for i, co in enumerate(new): sk.data[i].co = co
sk.value = 0.0
print("SB 形状キー %s を作った（値0のまま。着せたときだけ1にする）" % name)

bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True)
print("SB 書き出し", DST, os.path.getsize(DST))
