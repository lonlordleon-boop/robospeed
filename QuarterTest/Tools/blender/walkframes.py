# -*- coding: utf-8 -*-
"""コマごとの腰・両足の位置を並べて出す（診断用）。"""
import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
SRC, CLIP = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
act = bpy.data.actions.get(CLIP)
if arm.animation_data is None: arm.animation_data_create()
arm.animation_data.action = act
f0, f1 = act.frame_range
aw = arm.matrix_world
def P(n): return aw @ arm.pose.bones[n].head
arm.animation_data.action = None; bpy.context.view_layer.update()
rest = {n: P(n).copy() for n in ("Hips","LeftFoot","RightFoot","LeftToeBase","RightToeBase","head_end")}
print("WF rest LeftFoot %s RightFoot %s LeftToe %s RightToe %s Hips %s" % tuple(tuple(round(v,3) for v in rest[n]) for n in ("LeftFoot","RightFoot","LeftToeBase","RightToeBase","Hips")))
arm.animation_data.action = act
N=16
for k in range(N):
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
    h=P("Hips"); l=P("LeftFoot"); r=P("RightFoot"); lt=P("LeftToeBase"); rt=P("RightToeBase")
    print("WF %2d hips(%+.3f %+.3f %+.3f)  L(%+.3f %+.3f z%.3f toe%.3f)  R(%+.3f %+.3f z%.3f toe%.3f)" % (k, h.x-rest["Hips"].x, h.y-rest["Hips"].y, h.z-rest["Hips"].z, l.x, l.y, l.z, lt.z, r.x, r.y, r.z, rt.z))
