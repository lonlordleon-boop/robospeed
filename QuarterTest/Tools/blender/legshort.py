# -*- coding: utf-8 -*-
"""脚だけを縮める（「今の頭身だと中学生くらいにみえる…足だけを10cm縮めてみて」）。
   足首の少し上（ZA）から股関節（ZC）までを高さ方向に縮め、合計 CUT だけ低くする。境目は 2cm でなめらかにつなぐ。
   足首より下（靴）は変えない。股関節より上（胴・腕・頭）は形を変えずに CUT だけ下げる。
   腕・手の頂点は（重みの割合だけ）胴と同じく下げるだけにして、脚と一緒に縮まないようにする。
   骨も同じ写し方で動かす。動き（クリップ）は外して書き出す（あとで作り直す）。
   実行: blender -b --factory-startup -P legshort.py -- 入力.glb 出力.glb [CUT 0.10] [ZA 0.13]"""
import bpy, sys, numpy as np
from mathutils import Vector, Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT = a[0], a[1]
CUT = float(a[2]) if len(a) > 2 else 0.10
ZA = float(a[3]) if len(a) > 3 else 0.13
RAMP = 0.02
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
if arm.animation_data:
    for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
    arm.animation_data.action = None
for ac in list(bpy.data.actions): bpy.data.actions.remove(ac)
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
AW = arm.matrix_world
ZC = min((AW @ arm.data.bones[s + 'UpLeg'].head_local).z for s in ('Left', 'Right'))   # 股関節の高さ（m）
K = 1 - CUT / (ZC - ZA)
print("LS 股関節 %.3f  足首の上 %.3f  縮める割合 %.3f" % (ZC, ZA, K))
# 高さの写し方 f(z) = z − (1−K)·∫mask（mask は ZA〜ZC で 1、境目は余弦でなめらか）
G = np.arange(-0.2, 2.5, 0.0002)
def ramp(x): return 0.5 - 0.5 * np.cos(np.pi * np.clip(x, 0, 1))
mask = ramp((G - (ZA - RAMP)) / (2 * RAMP)) * (1 - ramp((G - (ZC - RAMP)) / (2 * RAMP)))
F = G - (1 - K) * np.concatenate([[0], np.cumsum((mask[1:] + mask[:-1]) * 0.5 * np.diff(G))])
def f(z): return float(np.interp(z, G, F))
print("LS 確認 f(ZC+0.05)-z = %.4f  f(0.05)-z = %.4f" % (f(ZC + 0.05) - ZC - 0.05, f(0.05) - 0.05))
# ---- メッシュ ----
MW = me.matrix_world; MWi = MW.inverted()
gname = {g.index: g.name for g in me.vertex_groups}
def is_arm(n): return any(k in n for k in ('Shoulder', 'Arm', 'Hand'))
moved = 0
for v in me.data.vertices:
    w = v.co.copy(); wp = MW @ w
    tot = sum(g.weight for g in v.groups) or 1.0
    wa = sum(g.weight for g in v.groups if is_arm(gname[g.group])) / tot
    nz = wa * (wp.z - CUT) + (1 - wa) * f(wp.z)
    v.co = MWi @ Vector((wp.x, wp.y, nz)); moved += 1
me.data.update()
# ---- 骨 ----
bpy.context.view_layer.objects.active = arm; arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
AWi = AW.inverted()
def fv(p):
    wp = AW @ p
    return AWi @ Vector((wp.x, wp.y, f(wp.z)))
new = {eb.name: (fv(eb.head), fv(eb.tail)) for eb in arm.data.edit_bones}
for eb in arm.data.edit_bones:
    eb.head, eb.tail = new[eb.name]
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
zs = [(me.matrix_world @ v.co).z for v in em.vertices]
print("LS 頂点 %d  高さ %.3f〜%.3f（%.3f m）" % (moved, min(zs), max(zs), max(zs) - min(zs)))
me.evaluated_get(dg).to_mesh_clear()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=False, export_skins=True, export_yup=True)
print("LS 書き出し", OUT)
