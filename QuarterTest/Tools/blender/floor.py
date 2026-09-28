# クリップの各コマで、いちばん低い頂点の高さを測る（浮き・めり込みの確認）
import bpy,sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]; CLIP=a[1]; N=int(a[2]) if len(a)>2 else 16
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o,do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE'); me=next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act
f0,f1=act.frame_range
H=None; vals=[]
for k in range(N):
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
    dg=bpy.context.evaluated_depsgraph_get(); ev=me.evaluated_get(dg); m=ev.to_mesh()
    P=np.array([tuple(ev.matrix_world@v.co) for v in m.vertices]); ev.to_mesh_clear()
    if H is None: H=P[:,2].max()-P[:,2].min()
    vals.append(P[:,2].min())
v=np.array(vals)
print("FL %s 最低点(cm) %s"%(CLIP, " ".join("%.1f"%(x*100) for x in v)))
print("FL 全体 最小%.1fcm 最大%.1fcm 身長比 最大浮き%.1f%%"%(v.min()*100, v.max()*100, 100*v.max()/H))
