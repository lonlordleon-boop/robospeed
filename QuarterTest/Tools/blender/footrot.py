# -*- coding: utf-8 -*-
"""足の骨の向きをコマごとに出す：靴の底の向き（横倒し=roll）、つま先の上下（pitch）、つま先の左右（yaw）。
   素の姿勢での向きを基準にした差ではなく、ワールドの絶対角。"""
import bpy, sys, math
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
SRC, CLIP = a[0], a[1]; N=16
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
if arm.animation_data is None: arm.animation_data_create()
aw=arm.matrix_world
def M(n): return aw @ arm.pose.bones[n].matrix
# 素の姿勢で「足の下向き」「つま先向き」を骨のローカルで求める
arm.animation_data.action=None; bpy.context.view_layer.update()
loc={}
for s in ('Left','Right'):
    Mf=M(s+'Foot'); toe=(aw@arm.pose.bones[s+'ToeBase'].head)-(aw@arm.pose.bones[s+'Foot'].head)
    R=Mf.to_3x3(); Ri=R.inverted()
    loc[s]=(Ri@Vector((0,0,-1)), Ri@toe.normalized())   # ローカルでの下向き・つま先向き
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
print("FR 底の横倒し: 靴底の法線が左右へ倒れた角（+は底が左を向く）。つま先上下: +で上向き。つま先左右: +で左")
for k in range(N):
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
    out=[]
    for s in ('Left','Right'):
        R=M(s+'Foot').to_3x3(); dn=R@loc[s][0]; tf=R@loc[s][1]
        roll=math.degrees(math.atan2(dn.x,-dn.z)); pitch=math.degrees(math.asin(max(-1,min(1,tf.z)))); yaw=math.degrees(math.atan2(tf.x,-tf.y))
        out.append("%s 底横倒し%+4.0f つま先上下%+4.0f 左右%+4.0f"%(s[0],roll,pitch,yaw))
    print("FR %2d  "%k+"  |  ".join(out))
