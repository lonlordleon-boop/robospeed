# -*- coding: utf-8 -*-
"""頭の重みが混ざった頂点が、首の関節からどの位置（高さ・前後）にあるかを表にする（髪と襟を分ける基準を決めるため）。"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]; SRC=a[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith('Icosphere'))
vg={g.index:g.name for g in mesh.vertex_groups}
rest=np.array([tuple(mesh.matrix_world @ v.co) for v in mesh.data.vertices])
H=rest[:,2].max()-rest[:,2].min()
nk=arm.matrix_world @ arm.pose.bones['neck'].head
headW=np.zeros(len(rest))
for v in mesh.data.vertices:
    for g in v.groups:
        if vg[g.group] in ('Head','headfront'): headW[v.index]+=g.weight
sel=np.where((headW>0.05)&(headW<0.98))[0]
dz=(rest[sel,2]-nk.z)/H*100; dy=(rest[sel,1]-nk.y)/H*100   # +dy は後ろ
print("HH 首関節 z=%.3f y=%.3f 身長%.3f  対象頂点 %d"%(nk.z,nk.y,H,len(sel)))
zb=[-15,-10,-5,0,5,10,20,40]; yb=[-15,-5,0,5,10,15,30]
print("HH 高さ(首基準%%)＼前後(%%: +後ろ)  " + " ".join("%5s"%("%d..%d"%(yb[j],yb[j+1])) for j in range(len(yb)-1)))
for i in range(len(zb)-1):
    row=[]
    for j in range(len(yb)-1):
        m=(dz>=zb[i])&(dz<zb[i+1])&(dy>=yb[j])&(dy<yb[j+1]); row.append(m.sum())
    print("HH %4d..%-4d                   "%(zb[i],zb[i+1]) + " ".join("%5d"%x for x in row))
