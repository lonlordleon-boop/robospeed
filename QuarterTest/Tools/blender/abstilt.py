# -*- coding: utf-8 -*-
"""左右対の関節の高さ差から、骨盤・肩・目（頭）の絶対的な横倒し角を出す（素の姿勢に依存しない）。+は左が高い。"""
import bpy, sys, math
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIPS = a[1].split(',')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
if arm.animation_data is None: arm.animation_data_create()
aw = arm.matrix_world
def P(n): return aw @ arm.pose.bones[n].head
def tilt(l,r):
    L=P(l); R=P(r); return math.degrees(math.atan2(L.z-R.z, L.x-R.x))
def row(tag):
    print("AT %-14s 骨盤%+5.1f  肩%+5.1f  頭-首の横ずれ%+.3f  首-腰の横ずれ%+.3f  頭y%+.3f" % (tag, tilt("LeftUpLeg","RightUpLeg"), tilt("LeftShoulder","RightShoulder"),
          P("head_end").x-P("neck").x, P("neck").x-P("Hips").x, P("head_end").y-P("Hips").y))
arm.animation_data.action=None; bpy.context.view_layer.update(); row("rest")
for c in CLIPS:
    act=bpy.data.actions.get(c); arm.animation_data.action=act; f0,f1=act.frame_range
    for k in range(8):
        bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/8))); bpy.context.view_layer.update(); row("%s %d"%(c,k))
