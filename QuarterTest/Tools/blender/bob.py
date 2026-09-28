# -*- coding: utf-8 -*-
"""腰の高さと、一番低い足の高さを細かい間隔で出す（ガクンと落ちるコマを探す）。"""
import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
SRC, CLIP = a[0], a[1]; N=32
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith('Icosphere'))
if arm.animation_data is None: arm.animation_data_create()
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
aw=arm.matrix_world
def P(n): return aw @ arm.pose.bones[n].head
def lowest():
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    z=min((ev.matrix_world @ v.co).z for v in me.vertices); ev.to_mesh_clear(); return z
H=P("head_end").z
for k in range(N):
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
    h=P("Hips").z; lo=lowest(); lf=min(P("LeftFoot").z,P("LeftToeBase").z); rf=min(P("RightFoot").z,P("RightToeBase").z)
    print("BB %2d 腰%.3f メッシュ最下点%+.3f 左足%.3f 右足%.3f 腰-最下点%.3f"%(k,h,lo,lf,rf,h-lo))
