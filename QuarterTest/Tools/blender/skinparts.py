# -*- coding: utf-8 -*-
"""肌色に塗られた面を「つながり」でかたまりに分け、大きさと場所を一覧にする。
   顔や耳は大きなかたまり、髪の上に乗った肌色は小さな孤立したかたまりになる。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,TEX=a[0],a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
neckz=(arm.matrix_world@arm.pose.bones['neck'].head).z
mw=mesh.matrix_world
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
NF=len(me.polygons); K=np.zeros(NF,int); ctr=np.zeros((NF,3))
for f in me.polygons:
    uv=np.mean([list(uvl[li].uv) for li in f.loop_indices],0)
    c=px[int(uv[1]*H)%H,int(uv[0]*W)%W,:3]; r,g,b=c
    K[f.index]= 1 if (r>0.66 and g>0.40 and b>0.30 and g<r*0.99 and b<g*1.10) else (2 if (r>0.28 and g<r*0.75 and b<r*0.55) else 0)
    ctr[f.index]=tuple(mw@f.center)
# 同じ位置の頂点でつながりを作る（UVの継ぎ目対策）
P=np.array([tuple(mw@v.co) for v in me.vertices])
key={}; rep=np.arange(len(P))
for v in range(len(P)):
    k=tuple(np.round(P[v],5))
    if k in key: rep[v]=key[k]
    else: key[k]=v
e2f={}
for f in me.polygons:
    vs=[rep[me.loops[li].vertex_index] for li in f.loop_indices]
    for i in range(len(vs)):
        e=tuple(sorted((vs[i],vs[(i+1)%len(vs)])))
        e2f.setdefault(e,[]).append(f.index)
skins=[i for i in range(NF) if K[i]==1 and ctr[i][2]>neckz]
S=set(skins); par={i:i for i in skins}
def find(x):
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
for e,fs in e2f.items():
    ss=[i for i in fs if i in S]
    for j in ss[1:]: par[find(ss[0])]=find(j)
grp={}
for i in skins: grp.setdefault(find(i),[]).append(i)
rows=sorted(((len(v),np.mean(ctr[v],0),v) for v in grp.values()),key=lambda x:-x[0])
print("SP 頭の肌色の面 %d、かたまり %d 個"%(len(skins),len(rows)))
for n,c,v in rows[:14]:
    print("SP   %4d面 中心(%.3f,%.3f,%.3f)"%(n,*c))
