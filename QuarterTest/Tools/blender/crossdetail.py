# -*- coding: utf-8 -*-
"""すれ違いのコマで、足の骨の位置と靴の内側の縁の位置を詳しく出す。"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIP=a[1]; FR=[float(x) for x in a[2].split(',')]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
vg={g.index:g.name for g in mesh.vertex_groups}
side=np.zeros(len(mesh.data.vertices),int); dom=['']*len(mesh.data.vertices)
for v in mesh.data.vertices:
    l=sum(g.weight for g in v.groups if vg[g.group] in ('LeftFoot','LeftToeBase'))
    r=sum(g.weight for g in v.groups if vg[g.group] in ('RightFoot','RightToeBase'))
    if l>0.6: side[v.index]=1
    elif r>0.6: side[v.index]=-1
    if v.groups: dom[v.index]=vg[max(v.groups,key=lambda g:g.weight).group]
dom=np.array(dom)
def verts():
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    v=np.array([tuple(ev.matrix_world @ x.co) for x in me.vertices]); ev.to_mesh_clear(); return v
aw=arm.matrix_world
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
for fr in FR:
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*fr))); bpy.context.view_layer.update()
    v=verts(); zmin=v[:,2].min()
    P=lambda n:(aw@arm.pose.bones[n].head)
    print("CD %.3f 骨x 左足%.3f 左つま先%.3f 右足%.3f 右つま先%.3f  y 左足%.3f 右足%.3f"%(fr,P('LeftFoot').x,P('LeftToeBase').x,P('RightFoot').x,P('RightToeBase').x,P('LeftFoot').y,P('RightFoot').y))
    L=v[side==1]; R=v[side==-1]
    Ls=L[L[:,2]<zmin+0.08]; Rs=R[R[:,2]<zmin+0.08]
    print("CD   靴(下8cm) 左 x%.3f..%.3f y%.3f..%.3f  右 x%.3f..%.3f y%.3f..%.3f"%(Ls[:,0].min(),Ls[:,0].max(),Ls[:,1].min(),Ls[:,1].max(),Rs[:,0].min(),Rs[:,0].max(),Rs[:,1].min(),Rs[:,1].max()))
    # 左靴の一番内側(xが小さい)の頂点の主な骨
    i=np.argmin(Ls[:,0]); j=np.argmax(Rs[:,0])
    print("CD   左靴の最内点 (%.3f,%.3f,%.3f)  右靴の最内点 (%.3f,%.3f,%.3f)"%(*Ls[i],*Rs[j]))
