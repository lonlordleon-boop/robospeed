# -*- coding: utf-8 -*-
"""メッシュから「トゲ」だけを取り除く。

   生成したモデルには、下着の裾や服の縁のような「色が切り替わる線」に沿って、
   1頂点だけが外へ飛び出した細いトゲが並ぶことがある。
   面としては正しくつながっているので穴ではないが、上から服を着せると
   そのトゲだけが服を突き抜けて、白い破片や「股に穴が開いている」ように見える。

   全体をならす meshsmooth.py と違い、こちらは飛び出している頂点だけを動かす。
   頂点ごとに、辺でつながった隣の平均の位置を求め、そこから離れている距離を測る。
   しきい値より離れていればトゲとみなし、隣の平均へ寄せる。ふつうの面は動かない。

   UV の継ぎ目で同じ位置の頂点が分かれているので、先に位置でまとめてから測る。
   まとめないと、継ぎ目の頂点は隣が半分しか無く、まっとうな面までトゲと判定される。

   実行: blender -b --factory-startup -P despike.py -- 入力.glb 出力.glb
         [しきい値（辺の長さに対する割合）既定0.60] [回数 既定3] [残す高さ z下,z上 既定すべて]
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
THR = float(a[2]) if len(a) > 2 else 0.60   # 辺の長さの何倍ずれていたらトゲとみなすか
ITER = int(a[3]) if len(a) > 3 else 3
ZR = [float(v) for v in a[4].split(',')] if len(a) > 4 and a[4] else None

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
me = next(o for o in bpy.data.objects if o.type == 'MESH')
mesh = me.data
print("DS %s 頂点 %d 面 %d" % (me.name, len(mesh.vertices), len(mesh.polygons)))

# 同じ位置の頂点をまとめる（UV の継ぎ目で分かれているため）
key = {}
group = [0]*len(mesh.vertices)
for v in mesh.vertices:
    k = (round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))
    if k not in key: key[k] = len(key)
    group[v.index] = key[k]
ng = len(key)
members = [[] for _ in range(ng)]
for i, g in enumerate(group): members[g].append(i)
print("DS 位置でまとめた頂点 %d 個" % ng)

nbr = [set() for _ in range(ng)]
for e in mesh.edges:
    a_, b_ = group[e.vertices[0]], group[e.vertices[1]]
    if a_ != b_: nbr[a_].add(b_); nbr[b_].add(a_)

# 測るのは world 座標（メートル）。glb の中の座標は骨の都合で縮んでいることがある
MW = me.matrix_world
pos = np.zeros((ng, 3))
for g, ms in enumerate(members): pos[g] = tuple(MW @ mesh.vertices[ms[0]].co)

# 頂点ごとの辺の長さの平均。しきい値はこれに対する割合で見る。
# 絶対値で決めると、曲がった面（頭のような丸い所）まで全部トゲとみなしてしまった
elen = np.zeros(ng)
for g, ns in enumerate(nbr):
    if ns: elen[g] = np.linalg.norm(pos[list(ns)] - pos[g], axis=1).mean()
print("DS 辺の長さ 中央値 %.1f mm" % (np.median(elen[elen > 0])*1000))

total = 0
for it in range(ITER):
    avg = pos.copy()
    for g, ns in enumerate(nbr):
        if ns: avg[g] = pos[list(ns)].mean(axis=0)
    d = np.linalg.norm(pos - avg, axis=1)
    m = (elen > 0) & (d > THR * elen)
    if ZR is not None:
        m &= (pos[:,2] >= ZR[0]) & (pos[:,2] <= ZR[1])
    n = int(m.sum())
    if not n:
        print("DS %d回目: トゲなし" % (it+1)); break
    print("DS %d回目: トゲ %d 個（動かす中で一番大きいずれ %.1f mm）" % (it+1, n, d[m].max()*1000))
    pos[m] = avg[m]; total += n

if total:
    for g, ms in enumerate(members):
        for i in ms: mesh.vertices[i].co = MW.inverted() @ Vector(tuple(pos[g]))
    print("DS のべ %d 個を隣の平均へ寄せた" % total)

bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True)
print("DS 書き出し", DST, os.path.getsize(DST))
