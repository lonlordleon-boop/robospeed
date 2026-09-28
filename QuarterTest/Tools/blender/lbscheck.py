# -*- coding: utf-8 -*-
"""ある頂点について、各骨の剛体変換だけで動かした位置と、実際のスキン結果を比べる（骨ごとの整合性の確認）。"""
import bpy, sys
import numpy as np
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIP=a[1]; FR=float(a[2]); IDX=[int(x) for x in a[3].split(',')]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
vg={g.index:g.name for g in mesh.vertex_groups}
aw=arm.matrix_world
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
bpy.context.scene.frame_set(int(round(f0+(f1-f0)*FR))); bpy.context.view_layer.update()
dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
for i in IDX:
    v=mesh.data.vertices[i]; vb=mesh.matrix_world@v.co; actual=ev.matrix_world@me.vertices[i].co
    parts=[]; blend=Vector((0,0,0))
    for g in v.groups:
        n=vg[g.group]; pb=arm.pose.bones[n]
        T=aw@pb.matrix@pb.bone.matrix_local.inverted()@aw.inverted()
        p=T@vb; blend+=g.weight*p
        parts.append("%s w%.2f→(%.3f,%.3f,%.3f)"%(n,g.weight,p.x,p.y,p.z))
    print("LC idx%d 素(%.3f,%.3f,%.3f) 実際(%.3f,%.3f,%.3f) 合成(%.3f,%.3f,%.3f) | %s"%(i,vb.x,vb.y,vb.z,actual.x,actual.y,actual.z,blend.x,blend.y,blend.z," | ".join(parts)))
for n in ('LeftLeg','LeftFoot'):
    pb=arm.pose.bones[n]; print("LC 骨 %s 今の位置(%.3f,%.3f,%.3f) 素の位置(%.3f,%.3f,%.3f)"%(n,*(aw@pb.head),*(aw@pb.bone.head_local)))
ev.to_mesh_clear()
