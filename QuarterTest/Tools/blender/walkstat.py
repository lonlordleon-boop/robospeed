# -*- coding: utf-8 -*-
"""歩きの腰の左右・上下の揺れと、足の持ち上がり量を測る。"""
import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
SRC, CLIP = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
act = bpy.data.actions.get(CLIP)
if arm.animation_data is None: arm.animation_data_create()
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = act
f0, f1 = act.frame_range
aw = arm.matrix_world
def P(n): return aw @ arm.pose.bones[n].head
# 素の姿勢（アクション無し）
arm.animation_data.action = None; bpy.context.view_layer.update()
rest = {n: P(n).copy() for n in ("Hips","LeftFoot","RightFoot","LeftToeBase","RightToeBase","head_end")}
H = rest["head_end"].z - min(rest["LeftToeBase"].z, rest["RightToeBase"].z)
arm.animation_data.action = act
hx=[]; hy=[]; lf=[]; rf=[]
N=24
for k in range(N):
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
    h=P("Hips"); hx.append(h.x-rest["Hips"].x); hy.append(h.z-rest["Hips"].z)
    lf.append(min(P("LeftFoot").z, P("LeftToeBase").z) - min(rest["LeftFoot"].z, rest["LeftToeBase"].z))
    rf.append(min(P("RightFoot").z, P("RightToeBase").z) - min(rest["RightFoot"].z, rest["RightToeBase"].z))
pc=lambda v: 100*v/H
print("WS %s 身長%.3f" % (CLIP, H))
print("WS 腰の左右揺れ  %+.1f%% 〜 %+.1f%%（幅 %.1f%%）  平均 %+.1f%%" % (pc(min(hx)), pc(max(hx)), pc(max(hx)-min(hx)), pc(sum(hx)/N)))
print("WS 腰の上下     %+.1f%% 〜 %+.1f%%" % (pc(min(hy)), pc(max(hy))))
print("WS 左足の高さ   最低 %+.1f%%  最高 %+.1f%%   右足  最低 %+.1f%%  最高 %+.1f%%" % (pc(min(lf)), pc(max(lf)), pc(min(rf)), pc(max(rf))))
