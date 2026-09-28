# -*- coding: utf-8 -*-
"""すれ違いのコマで、左靴の一番内側にある頂点の重みの内訳を出す（何に引っ張られているかを知る）。"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIP=a[1]; FR=float(a[2])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
vg={g.index:g.name for g in mesh.vertex_groups}
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
bpy.context.scene.frame_set(int(round(f0+(f1-f0)*FR))); bpy.context.view_layer.update()
dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
pos=np.array([tuple(ev.matrix_world@v.co) for v in me.vertices]); ev.to_mesh_clear()
zmin=pos[:,2].min()
cands=[]
for v in mesh.data.vertices:
    w={vg[g.group]:g.weight for g in v.groups if g.weight>0.005}
    if w.get('LeftFoot',0)+w.get('LeftToeBase',0)>0.6 and pos[v.index,2]<zmin+0.08:
        cands.append((pos[v.index,0],v.index,w))
cands.sort(key=lambda x:x[0])
aw=arm.matrix_world
print("IE 左足骨 x=%.3f  左靴の内側の頂点（xが小さい順）:"%(aw@arm.pose.bones['LeftFoot'].head).x)
for x,i,w in cands[:8]:
    print("IE   x=%.3f idx=%d 位置(%.3f,%.3f,%.3f) 重み %s"%(x,i,*pos[i],{k:round(v,2) for k,v in w.items()}))
