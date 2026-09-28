# -*- coding: utf-8 -*-
"""面の向き（表裏）がそろっていない箇所を探す。
   Unity は裏面を描かないので、向きが逆の面はそこだけ穴が開いたように見え、
   奥にあるもの（肌など）が透けて見える。ブラウザ側は両面描画にしているので気づけない。"""
import bpy, bmesh, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
if SRC.lower().endswith('.fbx'): bpy.ops.import_scene.fbx(filepath=SRC)
else: bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
before=np.array([tuple(f.normal) for f in me.polygons])
ctr=np.array([tuple(f.center) for f in me.polygons])
bm=bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(me); bm.free(); me.update()
after=np.array([tuple(f.normal) for f in me.polygons])
dot=(before*after).sum(1)
flip=np.where(dot<0)[0]
H=max(v.co.z for v in me.vertices)-min(v.co.z for v in me.vertices); base=min(v.co.z for v in me.vertices)
print("FL 面 %d 個中、向きが逆だった面 %d 個 (%.2f%%)"%(len(me.polygons),len(flip),100*len(flip)/len(me.polygons)))
if len(flip):
    c=ctr[flip]
    used=np.zeros(len(flip),bool); groups=[]
    for i in range(len(flip)):
        if used[i]: continue
        d=np.linalg.norm(c-c[i],axis=1); m=(d<0.05)&(~used); used|=m; groups.append((int(m.sum()),c[m].mean(0)))
    groups.sort(reverse=True,key=lambda x:x[0])
    for n,p in groups[:10]:
        print("FL   %4d面のかたまり 位置(%.3f,%.3f,%.3f) 高さ%.0f%%"%(n,p[0],p[1],p[2],100*(p[2]-base)/H))
