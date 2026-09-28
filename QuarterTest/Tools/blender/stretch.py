# -*- coding: utf-8 -*-
"""アニメの各コマで、素の姿勢より極端に伸びた辺を探す（穴・トゲの原因を突き止める）。
   実行: blender -b --factory-startup -P stretch.py -- 入力.glb クリップ名"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIPS=a[1].split(','); N=16
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
vg={g.index:g.name for g in mesh.vertex_groups}
E=np.array([tuple(e.vertices) for e in mesh.data.edges])
rest=np.array([tuple(mesh.matrix_world @ v.co) for v in mesh.data.vertices])
L0=np.linalg.norm(rest[E[:,0]]-rest[E[:,1]],axis=1)
H=rest[:,2].max()-rest[:,2].min()
def posed():
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    v=np.array([tuple(ev.matrix_world @ x.co) for x in me.vertices]); ev.to_mesh_clear(); return v
def wof(i): return {vg[g.group]:round(g.weight,2) for g in mesh.data.vertices[i].groups if g.weight>0.02}
for c in CLIPS:
    act=bpy.data.actions.get(c)
    if act is None: continue
    arm.animation_data.action=act; f0,f1=act.frame_range
    worst={}
    for k in range(N):
        bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
        p=posed(); L=np.linalg.norm(p[E[:,0]]-p[E[:,1]],axis=1)
        r=L/np.maximum(L0,1e-6)
        for ei in np.where((r>2.5)&(L>0.02))[0]:
            if r[ei]>worst.get(ei,(0,))[0]: worst[ei]=(r[ei],k,tuple(np.round(p[E[ei,0]],3)))
    items=sorted(worst.items(),key=lambda x:-x[1][0])
    print("ST %-11s 極端に伸びた辺 %d 本 / 全%d本"%(c,len(items),len(E)))
    for ei,(r,k,pos) in items[:6]:
        i,j=E[ei]
        print("ST    %.1f倍 コマ%d 位置%s 高さ%.0f%%  v%d %s / v%d %s"%(r,k,pos,100*(rest[i,2]-rest[:,2].min())/H,i,wof(i),j,wof(j)))
