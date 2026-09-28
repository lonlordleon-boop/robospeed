# -*- coding: utf-8 -*-
"""頭に付いているはずの頂点（首より上で、頭の重みが 0.3 以上）が、頭の骨と一緒に動かずにどれだけズレるかを
   クリップ・コマごとに測る。ズレの大きいコマを描画候補として出す。"""
import bpy, sys
import numpy as np
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIPS = a[1].split(','); N = 24
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
arm.animation_data.action=None; bpy.context.view_layer.update()
vg={g.index:g.name for g in mesh.vertex_groups}
rest=np.array([tuple(mesh.matrix_world @ v.co) for v in mesh.data.vertices])
neckz=(arm.matrix_world @ arm.pose.bones['neck'].head).z
headW=np.zeros(len(rest)); other={}
for v in mesh.data.vertices:
    for g in v.groups:
        n=vg[g.group]
        if n in ('Head','headfront'): headW[v.index]+=g.weight
        elif g.weight>0.02: other.setdefault(v.index,[]).append((n,round(g.weight,2)))
sel=np.where((rest[:,2]>neckz)&(headW>0.3)&(headW<0.98))[0]
print("HD 首より上で頭の重み0.3〜0.98の頂点", len(sel), "個（頭以外の骨も混ざる頂点）")
cnt={}
for i in sel:
    for n,w in other.get(i,[]): cnt[n]=cnt.get(n,0)+1
print("HD 混ざっている骨:", sorted(cnt.items(), key=lambda x:-x[1]))
Mrest=(arm.matrix_world @ arm.pose.bones['Head'].matrix).copy()
def posed():
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    v=np.array([tuple(ev.matrix_world @ x.co) for x in me.vertices]); ev.to_mesh_clear(); return v
H=rest[:,2].max()-rest[:,2].min()
for c in CLIPS:
    act=bpy.data.actions.get(c); arm.animation_data.action=act; f0,f1=act.frame_range
    best=(0,0)
    row=[]
    for k in range(N):
        fr=int(round(f0+(f1-f0)*k/N)); bpy.context.scene.frame_set(fr); bpy.context.view_layer.update()
        Mh=(arm.matrix_world @ arm.pose.bones['Head'].matrix) @ Mrest.inverted()
        Mn=np.array(Mh)
        rigid=(Mn[:3,:3] @ rest[sel].T).T + Mn[:3,3]
        v=posed()[sel]
        d=np.linalg.norm(v-rigid,axis=1); mx=d.max()/H*100
        row.append(mx)
        if mx>best[0]: best=(mx,k/N)
    print("HD %-10s ズレ最大(身長%%) コマごと: "%c + " ".join("%3.1f"%x for x in row) + "   最大 %.1f%% at %.3f"%best)
