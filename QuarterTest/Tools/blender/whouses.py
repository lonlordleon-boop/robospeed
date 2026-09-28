# -*- coding: utf-8 -*-
"""テクスチャの指定した画素を、どの部位の面が使っているかを調べる（UVの使い回しの確認）。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]; u,v=map(float,a[1].split(',')); RAD=int(a[2]) if len(a)>2 else 12
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
mw=mesh.matrix_world; uvl=me.uv_layers.active.data
hits=[]
for f in me.polygons:
    for li in f.loop_indices:
        du=(uvl[li].uv[0]-u)*2048; dv=(uvl[li].uv[1]-v)*2048
        if abs(du)<=RAD and abs(dv)<=RAD:
            hits.append((f.index, tuple(mw@f.center))); break
print("WU UV(%.4f,%.4f) の %d画素以内を使う面 %d"%(u,v,RAD,len(hits)))
if hits:
    P=np.array([h[1] for h in hits])
    # 高さでざっくり分類
    for lo,hi,nm in ((0.0,0.45,'脚・靴'),(0.45,0.60,'胴・腕'),(0.60,0.78,'顔・耳の高さ'),(0.78,0.95,'頭の上'),(0.95,2.0,'てっぺん・リボン')):
        m=(P[:,2]>=lo)&(P[:,2]<hi)
        if m.sum(): print("WU   %s: %d面  x %.2f..%.2f y %.2f..%.2f"%(nm,m.sum(),P[m][:,0].min(),P[m][:,0].max(),P[m][:,1].min(),P[m][:,1].max()))
