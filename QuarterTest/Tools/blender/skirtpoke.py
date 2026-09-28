# -*- coding: utf-8 -*-
"""スカートを脚が突き抜けていないかを、動きのコマごとに数える（調べるだけ。書き出さない）。
   太ももの肌の頂点（素の姿勢で高さ ZLO〜ZHI・脚の骨から 7cm 以内・脚の骨の重み 0.9 以上）へ、左右の股関節の真ん中から線を引き、
   途中でスカートの面（素の姿勢で高さ ZLO〜ZHI・脚の骨から 9cm より外・明るい）に当たったら「肌がスカートの外に出ている」と数える。
   実行: blender -b --factory-startup -P skirtpoke.py -- 入力.glb [ZLO 0.35] [ZHI 0.53]"""
import bpy, bmesh, sys, colorsys, numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_point_line
a = sys.argv[sys.argv.index("--")+1:]; SRC = a[0]
ZLO = float(a[1]) if len(a) > 1 else 0.35
ZHI = float(a[2]) if len(a) > 2 else 0.53
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
tracks = [(t.name, t.strips[0].action) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
P0 = np.array([tuple(me.matrix_world @ v.co) for v in m.vertices])
def bh(n): return arm.matrix_world @ arm.data.bones[n].head_local
LSEG = [(bh(s + 'UpLeg'), bh(s + 'Leg')) for s in ('Left', 'Right')]
def legdist(p):
    pv = Vector(p); best = 9.0
    for h, t in LSEG:
        q, f = intersect_point_line(pv, h, t); f = min(1.0, max(0.0, f)); best = min(best, (pv - (h + (t - h) * f)).length)
    return best
gi = {g.index: g.name for g in me.vertex_groups}
LW = np.array([sum(e.weight for e in v.groups if gi[e.group].endswith(('UpLeg', 'Leg'))) for v in m.vertices])
skin = [i for i in range(len(P0)) if ZLO <= P0[i][2] <= ZHI - 0.04 and LW[i] >= 0.9 and legdist(P0[i]) < 0.07]
skf = []
for p in m.polygons:
    vs = list(p.vertices); c = P0[vs].mean(0)
    if not (ZLO <= c[2] <= ZHI) or legdist(c) < 0.09: continue
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    if colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])[2] < 0.5: continue
    skf.append(vs)
print("PK 太ももの肌の頂点 %d・スカートの面 %d" % (len(skin), len(skf)))
YC = float((bh('LeftUpLeg') + bh('RightUpLeg')).y / 2)      # 前後の分かれ目（股関節）
def pos():
    dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
    P = [me.matrix_world @ v.co for v in em.vertices]; me.evaluated_get(dg).to_mesh_clear(); return P
for nm, act in tracks:
    arm.animation_data.action = act; f0, f1 = map(int, act.frame_range); worst = (0, 0); tot = 0; totF = 0
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f); bpy.context.view_layer.update(); P = pos()
        tree = BVHTree.FromPolygons([P[i] for i in range(len(P))], skf)
        pl = arm.matrix_world @ arm.pose.bones['LeftUpLeg'].head; pr = arm.matrix_world @ arm.pose.bones['RightUpLeg'].head
        o = (pl + pr) / 2; n = 0
        for i in skin:
            d = P[i] - o; L = d.length
            hit = tree.ray_cast(o, d.normalized(), L - 0.004)
            if hit[0] is not None:
                n += 1
                if P0[i][1] < YC: totF += 1          # 素の姿勢で前側の肌
        tot += n
        if n > worst[0]: worst = (n, f)
    print("PK %-10s 突き抜けた肌の頂点：いちばん多いコマ %d 個（%d コマ目）・全コマの合計 %d（うち前 %d・後ろ %d）" % (nm, worst[0], worst[1], tot, totF, tot - totF))
