# -*- coding: utf-8 -*-
"""メッシュを「つながり」で塊（パーツ）に分け、それぞれの大きさ・高さ・代表色を出す。
   同じ位置の頂点（UVの継ぎ目で分かれたもの）は先につないでから数える。"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh = next(o for o in bpy.data.objects if o.type=='MESH')
arm  = next(o for o in bpy.data.objects if o.type=='ARMATURE')
vg={g.index:g.name for g in mesh.vertex_groups}
P=np.array([tuple(mesh.matrix_world @ v.co) for v in mesh.data.vertices]); nv=len(P)
H=P[:,2].max()-P[:,2].min()
par=list(range(nv))
def find(x):
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
key={}
for v in range(nv):
    k=tuple(np.round(P[v],5))
    if k in key: par[find(v)]=find(key[k])
    else: key[k]=v
for e in mesh.data.edges:
    a_,b_=e.vertices; par[find(a_)]=find(b_)
root=np.array([find(v) for v in range(nv)])
uniq,counts=np.unique(root,return_counts=True)
order=np.argsort(-counts)
print("PT 頂点 %d、パーツ %d 個"%(nv,len(uniq)))
for oi in order[:12]:
    r=uniq[oi]; m=root==r; pts=P[m]
    # 主な骨
    cnt={}
    for v in np.where(m)[0][::7]:
        for g in mesh.data.vertices[v].groups:
            if g.weight>0.3: cnt[vg[g.group]]=cnt.get(vg[g.group],0)+1
    top=sorted(cnt.items(),key=lambda x:-x[1])[:4]
    print("PT  塊 %6d頂点 高さ %3.0f%%..%3.0f%%  x %+.2f..%+.2f y %+.2f..%+.2f  主な骨 %s"%(
        counts[oi], 100*(pts[:,2].min()-P[:,2].min())/H, 100*(pts[:,2].max()-P[:,2].min())/H,
        pts[:,0].min(),pts[:,0].max(),pts[:,1].min(),pts[:,1].max(), top))
