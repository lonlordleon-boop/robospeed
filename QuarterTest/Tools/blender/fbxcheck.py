# -*- coding: utf-8 -*-
"""Unity が実際に読む FBX を読み込んで、極端に伸びる辺を数える（GLB での修正が FBX まで届いているかの確認）。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]; CLIPS=a[1].split(',')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh=next(o for o in bpy.data.objects if o.type=='MESH')
print("FX メッシュ",mesh.name,"頂点",len(mesh.data.vertices),"アクション",[a.name for a in bpy.data.actions])
vg={g.index:g.name for g in mesh.vertex_groups}
if arm.animation_data is None: arm.animation_data_create()
E=np.array([tuple(e.vertices) for e in mesh.data.edges])
rest=np.array([tuple(mesh.matrix_world@v.co) for v in mesh.data.vertices])
L0=np.linalg.norm(rest[E[:,0]]-rest[E[:,1]],axis=1)
def posed():
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    v=np.array([tuple(ev.matrix_world@x.co) for x in me.vertices]); ev.to_mesh_clear(); return v
for c in CLIPS:
    act=next((a for a in bpy.data.actions if c in a.name),None)
    if act is None: print("FX",c,"見つからず"); continue
    arm.animation_data.action=act; f0,f1=act.frame_range
    worst={}
    for k in range(16):
        bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/16))); bpy.context.view_layer.update()
        p=posed(); L=np.linalg.norm(p[E[:,0]]-p[E[:,1]],axis=1); r=L/np.maximum(L0,1e-6)
        for ei in np.where((r>2.5)&(L>0.02))[0]:
            if r[ei]>worst.get(ei,(0,))[0]: worst[ei]=(r[ei],k)
    items=sorted(worst.items(),key=lambda x:-x[1][0])
    print("FX %-14s 極端に伸びた辺 %d 本"%(act.name,len(items)))
    for ei,(r,k) in items[:3]:
        i,j=E[ei]
        w=lambda v:{vg[g.group]:round(g.weight,2) for g in mesh.data.vertices[v].groups if g.weight>0.02}
        print("FX    %.1f倍 コマ%d  v%d %s / v%d %s"%(r,k,i,w(i),j,w(j)))
