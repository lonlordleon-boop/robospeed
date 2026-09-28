# -*- coding: utf-8 -*-
"""指定した面番号のテクスチャ画素を緑に塗る（どの面がどこに出るかの確認用）。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]; IDX=[int(x) for x in a[3].split(',')]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
me.calc_loop_triangles()
out=px.copy(); n=0
for t in me.loop_triangles:
    if t.polygon_index not in IDX: continue
    uv=np.array([uvl[li].uv for li in t.loops],float)
    xs=uv[:,0]*W; ys=uv[:,1]*H
    x0=max(0,int(np.floor(xs.min()))-1); x1=min(W-1,int(np.ceil(xs.max()))+1)
    y0=max(0,int(np.floor(ys.min()))-1); y1=min(H-1,int(np.ceil(ys.max()))+1)
    gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
    dd=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
    if abs(dd)<1e-12: continue
    l1=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/dd
    l2=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/dd
    l3=1-l1-l2; m=(l1>=-0.25)&(l2>=-0.25)&(l3>=-0.25)
    sub=out[y0:y1+1,x0:x1+1]; sub[m]=[0,1,0,1]; out[y0:y1+1,x0:x1+1]=sub; n+=int(m.sum())
print("PF 塗った画素",n)
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("PF 書き出し",OUT)
