# -*- coding: utf-8 -*-
"""周りの頂点から大きく離れて飛び出した頂点（トゲ）を探す。
   実行: blender -b --factory-startup -P spikes.py -- 入力.glb クリップ"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]; CLIP=a[1]; N=12
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh=next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
vg={g.index:g.name for g in mesh.vertex_groups}
nv=len(mesh.data.vertices)
nb=[[] for _ in range(nv)]
for e in mesh.data.edges:
    a_,b_=e.vertices; nb[a_].append(b_); nb[b_].append(a_)
rest=np.array([tuple(mesh.matrix_world@v.co) for v in mesh.data.vertices])
H=rest[:,2].max()-rest[:,2].min()
def dev(P):
    d=np.zeros(nv)
    for v in range(nv):
        if not nb[v]: continue
        d[v]=np.linalg.norm(P[v]-P[nb[v]].mean(0))
    return d
d0=dev(rest)
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
worst={}
for k in range(N):
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    P=np.array([tuple(ev.matrix_world@x.co) for x in me.vertices]); ev.to_mesh_clear()
    d=dev(P); out=d-d0
    for v in np.where(out>0.012)[0]:
        if out[v]>worst.get(v,(0,))[0]: worst[v]=(out[v],k,tuple(np.round(P[v],3)))
items=sorted(worst.items(),key=lambda x:-x[1][0])
print("SK 飛び出した頂点 %d 個"%len(items))
for v,(o,k,p) in items[:10]:
    w={vg[g.group]:round(g.weight,2) for g in mesh.data.vertices[v].groups if g.weight>0.02}
    print("SK   v%-6d はみ出し%.3f (身長比%.1f%%) コマ%d 位置%s 高さ%.0f%% %s"%(v,o,100*o/H,k,p,100*(rest[v,2]-rest[:,2].min())/H,w))
