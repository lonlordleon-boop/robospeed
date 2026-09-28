# -*- coding: utf-8 -*-
"""顔の前面で、面の「張り出し量（髪の房らしさ）」と、テクスチャの色分け（肌／髪）の関係を調べる。"""
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
P=np.array([tuple(mw@v.co) for v in me.vertices]); nv=len(P)
N=np.array([tuple((mw.to_3x3()@v.normal).normalized()) for v in me.vertices])
key={}; rep=np.arange(nv)
for v in range(nv):
    k=tuple(np.round(P[v],5))
    if k in key: rep[v]=key[k]
    else: key[k]=v
nb=[[] for _ in range(nv)]
for e in me.edges:
    a_,b_=rep[e.vertices[0]],rep[e.vertices[1]]; nb[a_].append(b_); nb[b_].append(a_)
head=P[:,2]>neckz
Q=P.copy()
for _ in range(40):
    Q2=Q.copy()
    for v in range(nv):
        if head[v] and rep[v]==v and nb[v]: Q2[v]=0.5*Q[v]+0.5*Q[nb[v]].mean(0)
    Q=Q2
for v in range(nv):
    if rep[v]!=v: Q[v]=Q[rep[v]]
pro=((P-Q)*N).sum(1)
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
rows=[]
for f in me.polygons:
    c=mw@f.center
    if c.z<neckz or c.y>-0.15: continue
    uv=np.array([uvl[li].uv for li in f.loop_indices])
    col=np.mean([px[int(np.clip(u[1],0,.9999)*H),int(np.clip(u[0],0,.9999)*W),:3] for u in uv],0)
    r,g,b=col
    k = 1 if (r>0.68 and g>0.42 and b>0.32 and g<r*0.99 and b<g*1.08) else (2 if (r>0.28 and g<r*0.75 and b<r*0.55) else 0)
    pf=np.mean([pro[me.loops[li].vertex_index] for li in f.loop_indices])
    rows.append((pf,k,c.x,c.y,c.z))
R=np.array(rows)
print("FC 顔の前面の面 %d（肌%d 髪%d その他%d）"%(len(R),(R[:,1]==1).sum(),(R[:,1]==2).sum(),(R[:,1]==0).sum()))
for k,nm in ((1,'肌'),(2,'髪')):
    p=R[R[:,1]==k][:,0]
    if len(p): print("FC %s の張り出し量: 下位10%%=%.4f 中央=%.4f 上位10%%=%.4f"%(nm,np.percentile(p,10),np.median(p),np.percentile(p,90)))
for th in (0.008,0.010,0.012,0.015):
    a1=((R[:,1]==1)&(R[:,0]>th)).sum(); a2=((R[:,1]==2)&(R[:,0]<=th)).sum()
    print("FC しきい値%.3f: 張り出しているのに肌色 %d面、平らなのに髪色 %d面"%(th,a1,a2))
