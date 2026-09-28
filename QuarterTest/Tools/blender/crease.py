# -*- coding: utf-8 -*-
"""形の折れ目（面と面の角度が大きい辺）で頭の表面を区画に分け、
   区画ごとにテクスチャの色の多数派を調べる（塗りが形とずれていないかの確認）。"""
import bpy, sys, math
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,TEX=a[0],a[1]; ANG=float(a[2]) if len(a)>2 else 35.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
neckz=(arm.matrix_world@arm.pose.bones['neck'].head).z
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
NF=len(me.polygons); col=np.zeros((NF,3)); ctr=np.zeros((NF,3)); nrm=np.zeros((NF,3))
mw=mesh.matrix_world
for f in me.polygons:
    uv=np.array([uvl[li].uv for li in f.loop_indices])
    col[f.index]=np.mean([px[int(np.clip(u[1],0,.9999)*H),int(np.clip(u[0],0,.9999)*W),:3] for u in uv],0)
    ctr[f.index]=tuple(mw@f.center); nrm[f.index]=tuple((mw.to_3x3()@f.normal).normalized())
def cls(c):
    r,g,b=c
    if r>0.68 and g>0.42 and b>0.32 and g<r*0.99 and b<g*1.08: return 1
    if r>0.28 and g<r*0.75 and b<r*0.55: return 2
    return 0
K=np.array([cls(c) for c in col])
e2f={}
for f in me.polygons:
    for e in f.edge_keys: e2f.setdefault(e,[]).append(f.index)
par=list(range(NF))
def find(x):
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
cos=math.cos(math.radians(ANG))
head=ctr[:,2]>neckz
for e,fs in e2f.items():
    if len(fs)!=2: continue
    i,j=fs
    if not(head[i] and head[j]): continue
    if float(np.dot(nrm[i],nrm[j]))>cos: par[find(i)]=find(j)
reg={}
for i in range(NF):
    if not head[i]: continue
    reg.setdefault(find(i),[]).append(i)
big=sorted(reg.items(),key=lambda kv:-len(kv[1]))[:8]
print("CR 折れ目%.0f度で分けた区画（頭より上）: %d 個"%(ANG,len(reg)))
for r,fs in big:
    ks=[K[i] for i in fs]; c=np.mean(ctr[fs],0)
    print("CR   %5d面 中心(%.3f,%.3f,%.3f) 肌%d 髪%d その他%d"%(len(fs),*c,ks.count(1),ks.count(2),ks.count(0)))
