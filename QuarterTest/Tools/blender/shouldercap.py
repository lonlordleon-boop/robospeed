# -*- coding: utf-8 -*-
"""肩の上面を、腕でなく鎖骨の骨（LeftShoulder・RightShoulder）で動かす。形・骨・動き・絵はそのまま、重みだけ。
   お嬢様（小学生編）は肩の関節（Arm の骨の根元）が肩のいちばん上にあり、肩の上面の重みがほとんど腕だった。
   スキップで腕を真横まで上げる（70 度）と肩の上面が大きく動き、そこに乗る髪が 5〜6cm 引き伸ばされた（「肩にまだ髪が付いてる」）。
   人の体と同じく、腕を上げても肩の上はあまり動かないようにする。
   頂点ごとに、上腕の骨の線（肩の関節→ひじ）への投影の位置 t（0=関節、1=ひじ）を出し、
   腕の骨（Arm・ForeArm・Hand）の重みのうち (1 - k) を鎖骨の骨へ移す。k = なめらか((t - T0) / (T1 - T0))
   → t ≤ T0（関節より上・内側）は全部鎖骨、t ≥ T1（上腕の途中から先）はそのまま。骨の線から RMAX より遠い頂点は触らない。
   骨の線より下側（わきの下）はそのまま
   実行: blender -b --factory-startup -P shouldercap.py -- 入力.glb 出力.glb [T0 -0.05] [T1 0.35] [RMAX 0.07]"""
import bpy, sys, numpy as np
from mathutils.geometry import intersect_point_line
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
T0 = float(a[2]) if len(a) > 2 else -0.05
T1 = float(a[3]) if len(a) > 3 else 0.35
RMAX = float(a[4]) if len(a) > 4 else 0.07
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
gi = {g.index: g.name for g in me.vertex_groups}; gn = {g.name: g.index for g in me.vertex_groups}
def bh(n): return arm.matrix_world @ arm.data.bones[n].head_local
def sstep(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
n = 0; moved = 0.0
for s in ('Left', 'Right'):
    A, F = bh(s + 'Arm'), bh(s + 'ForeArm'); SH = gn[s + 'Shoulder']
    chain = {gn[x] for x in (s + 'Arm', s + 'ForeArm', s + 'Hand') if x in gn}
    for v in m.vertices:
        p = me.matrix_world @ v.co
        if (p.x > 0) != (s == 'Left'): continue
        q, t = intersect_point_line(p, A, F)
        if t > T1 or (p - q).length > RMAX: continue
        if (p - A).length > RMAX + 0.02: continue          # 関節から遠い胴の頂点は触らない
        cw = sum(e.weight for e in v.groups if e.group in chain)
        if cw < 1e-4: continue
        k = sstep((t - T0) / (T1 - T0))
        # 骨の線より上側だけ（下側＝わきの下まで鎖骨にすると、腕を上げた時にわきが伸びる）。上 0 → 下 2cm でなめらかに戻す
        d = (F - A).normalized(); up = (np.array((0, 0, 1.0)) - np.array(d) * d.z); up /= np.linalg.norm(up)
        below = -float(np.dot(np.array(p - q), up))
        k = k + (1 - k) * sstep(below / 0.02)
        mv = cw * (1 - k)
        if mv < 1e-3: continue
        for e in v.groups:
            if e.group in chain: e.weight *= k
        old = sum(e.weight for e in v.groups if e.group == SH)
        me.vertex_groups[SH].add([v.index], old + mv, 'REPLACE')
        n += 1; moved += mv
print("SC 肩の上面 %d 頂点：腕の重みを鎖骨へ（平均 %.2f）" % (n, moved / max(n, 1)))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("SC 書き出し", OUT)
