# -*- coding: utf-8 -*-
"""靴のメッシュ同士の最短距離をコマごとに測る（骨ではなく頂点で）。左右は頂点の重みで分ける。
   0 なら食い込み（くっ付き）。"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIPS = a[1].split(','); N = int(a[2]) if len(a)>2 else 16
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
vg={g.index:g.name for g in mesh.vertex_groups}
side=np.zeros(len(mesh.data.vertices),int)   # +1 左足, -1 右足
for v in mesh.data.vertices:
    l=sum(g.weight for g in v.groups if vg[g.group] in ('LeftFoot','LeftToeBase','LeftLeg'))
    r=sum(g.weight for g in v.groups if vg[g.group] in ('RightFoot','RightToeBase','RightLeg'))
    if l>0.6: side[v.index]=1
    elif r>0.6: side[v.index]=-1
def verts():
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    v=np.array([tuple(ev.matrix_world @ x.co) for x in me.vertices]); ev.to_mesh_clear(); return v
H=None
for c in CLIPS:
    act=bpy.data.actions.get(c); arm.animation_data.action=act; f0,f1=act.frame_range
    row=[]
    for k in range(N):
        bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
        v=verts()
        if H is None: H=v[:,2].max()-v[:,2].min()
        L=v[side==1]; R=v[side==-1]
        # 靴の部分だけ（足首より下）
        L=L[L[:,2]<L[:,2].min()+0.12*H]; R=R[R[:,2]<R[:,2].min()+0.12*H]
        d=np.sqrt(((L[:,None,:]-R[None,:,:])**2).sum(-1)).min()
        row.append(d/H*100)
    print("SG %-10s 靴同士の最短距離(身長%%): "%c + " ".join("%4.1f"%x for x in row))
