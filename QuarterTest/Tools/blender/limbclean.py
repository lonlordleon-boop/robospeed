# -*- coding: utf-8 -*-
"""手足の骨から遠く離れた頂点から、その骨の重みを外す。

   Meshy の自動リグは近さで重みを配るので、A字の姿勢だと手が腰のすぐ横にあるぶん、
   腰の肉に腕の重みが乗る。立ち姿や歩きでは目立たないが、走りのように腕を大きく振ると、
   腰の布や肌がそこだけ引っぱられて、辺が15倍に伸びる。穴やトゲに見える。

   頂点ごとに、その骨の「線分（頭から尾）」までの距離を測り、しきい値より遠ければ
   その骨の重みを0にする。残った重みは合計が1になるように割り直す。
   全部0になってしまう頂点は触らない（どこにも結ばれていない頂点を作らないため）。

   glTF ファイルの中は Y が上。骨の位置はノードの階層をたどって求める。

   実行: blender -b --factory-startup -P limbclean.py -- 入力.glb 出力.glb
         [骨の名前,...  既定 LeftArm,LeftForeArm,LeftHand,RightArm,RightForeArm,RightHand]
         [しきい値 m 既定0.05]
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
NAMES = a[2].split(',') if len(a) > 2 and a[2] else \
        ['LeftArm','LeftForeArm','LeftHand','RightArm','RightForeArm','RightHand']
THR = float(a[3]) if len(a) > 3 else 0.05

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()

def seg(name):
    b = arm.data.bones.get(name)
    if b is None: return None
    return (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local)

segs = {n: seg(n) for n in NAMES}
missing = [n for n, s in segs.items() if s is None]
if missing: print("LC 見つからない骨:", missing)

def dist_to(p, ab):
    a_, b_ = ab
    d = b_ - a_
    L = d.length_squared
    t = 0.0 if L < 1e-12 else max(0.0, min(1.0, (p - a_).dot(d) / L))
    return (p - (a_ + d * t)).length

total = 0
for me in [o for o in bpy.data.objects if o.type == 'MESH']:
    gi = {g.name: g.index for g in me.vertex_groups}
    idx = {gi[n]: n for n in NAMES if n in gi and segs.get(n)}
    if not idx: continue
    MW = me.matrix_world
    n = 0
    for v in me.data.vertices:
        p = MW @ v.co
        drop = [g for g in v.groups if g.group in idx and dist_to(p, segs[idx[g.group]]) > THR]
        if not drop: continue
        keep = sum(g.weight for g in v.groups if g not in drop)
        if keep <= 1e-6: continue                 # どこにも結ばれない頂点は作らない
        for g in drop: g.weight = 0.0
        s = sum(g.weight for g in v.groups)
        if s > 1e-9:
            for g in v.groups: g.weight = g.weight / s
        n += 1
    print("LC %s: %d 頂点から遠い骨の重みを外した" % (me.name, n))
    total += n
print("LC 合計 %d 頂点（しきい値 %.3f m、対象 %s）" % (total, THR, ','.join(NAMES)))

bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True)
print("LC 書き出し", DST, os.path.getsize(DST))
