# -*- coding: utf-8 -*-
"""面ごとにテクスチャの色を調べ、「まわりが髪なのに自分は肌色」の面を数えて場所を出す。
   2つ隣まで見て、髪が多数なら髪の面とみなす。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,TEX=a[0],a[1]
RATIO=float(a[2]) if len(a)>2 else 0.6
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
NF=len(me.polygons); col=np.zeros((NF,3)); ctr=np.zeros((NF,3))
for f in me.polygons:
    uv=np.array([uvl[li].uv for li in f.loop_indices])
    cs=[px[int(np.clip(u[1],0,.9999)*H),int(np.clip(u[0],0,.9999)*W),:3] for u in uv]
    col[f.index]=np.mean(cs,0)
    ctr[f.index]=np.mean([tuple(mesh.matrix_world@me.vertices[me.loops[li].vertex_index].co) for li in f.loop_indices],0)
def cls(c):
    r,g,b=c
    if r>0.68 and g>0.42 and b>0.32 and g<r*0.99 and b<g*1.08: return 1   # 肌
    if r>0.28 and g<r*0.75 and b<r*0.55: return 2                          # 髪
    return 0
K=np.array([cls(c) for c in col])
e2f={}
for f in me.polygons:
    for e in f.edge_keys: e2f.setdefault(e,[]).append(f.index)
nb=[[] for _ in range(NF)]
for f in me.polygons:
    for e in f.edge_keys: nb[f.index]+=[j for j in e2f.get(e,[]) if j!=f.index]
nb2=[list(set(sum([nb[j] for j in nb[i]],[])+nb[i]))for i in range(NF)]
bad=[]
for i in range(NF):
    if K[i]!=1: continue
    n=[K[j] for j in nb2[i] if j!=i]
    if not n: continue
    if n.count(2)/len(n) >= RATIO: bad.append(i)
print("BS 面 %d、髪に囲まれた肌色の面 %d（2つ隣までで髪が%.0f%%以上）"%(NF,len(bad),100*RATIO))
if bad:
    c=ctr[bad]; used=np.zeros(len(bad),bool); groups=[]
    for i in range(len(bad)):
        if used[i]: continue
        d=np.linalg.norm(c-c[i],axis=1); m=(d<0.03)&(~used); used|=m; groups.append((int(m.sum()),c[m].mean(0)))
    groups.sort(reverse=True,key=lambda x:x[0])
    for n,p in groups[:10]: print("BS   %4d面 位置(%.3f,%.3f,%.3f)"%(n,*p))
