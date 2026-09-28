# -*- coding: utf-8 -*-
"""指定した点のまわりの面について、色の種類とつながりを調べる（肌色の染みが髪に囲まれているかを確認）。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,TEX=a[0],a[1]
C=np.array([float(x) for x in a[2].split(',')]); RAD=float(a[3])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
mw=mesh.matrix_world
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
sel=[]
for f in me.polygons:
    c=np.array(tuple(mw@f.center))
    if np.linalg.norm(c-C)<=RAD: sel.append((f.index,c))
def col(fi):
    f=me.polygons[fi]; uv=np.mean([list(uvl[li].uv) for li in f.loop_indices],0)
    return px[int(uv[1]*H)%H,int(uv[0]*W)%W,:3]
def cls(c):
    r,g,b=c
    if r>0.66 and g>0.40 and b>0.30 and g<r*0.99 and b<g*1.10: return '肌'
    if r>0.28 and g<r*0.75 and b<r*0.55: return '髪'
    return '他'
ks={}
for fi,c in sel: ks[fi]=cls(col(fi))
n1=sum(1 for v in ks.values() if v=='肌'); n2=sum(1 for v in ks.values() if v=='髪')
print("LM 半径%.3f内の面 %d：肌%d 髪%d 他%d"%(RAD,len(sel),n1,n2,len(sel)-n1-n2))
# 肌の面のかたまり（つながり）を数える
e2f={}
for f in me.polygons:
    for e in f.edge_keys: e2f.setdefault(e,[]).append(f.index)
skins=[fi for fi,k in ks.items() if k=='肌']
par={i:i for i in skins}
def find(x):
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
for fi in skins:
    for e in me.polygons[fi].edge_keys:
        for j in e2f.get(e,[]):
            if j in par: par[find(fi)]=find(j)
grp={}
for fi in skins: grp.setdefault(find(fi),[]).append(fi)
print("LM   肌のかたまり %d 個: %s"%(len(grp),sorted([len(v) for v in grp.values()],reverse=True)[:6]))
for r,fs in sorted(grp.items(),key=lambda kv:-len(kv[1]))[:3]:
    p=np.array([dict(sel)[fi] for fi in fs])
    print("LM     %3d面 中心(%.3f,%.3f,%.3f) 広がり %.3f"%(len(fs),*p.mean(0),np.linalg.norm(p.max(0)-p.min(0))))
