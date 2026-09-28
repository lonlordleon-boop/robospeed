# -*- coding: utf-8 -*-
"""面が実際に使っている画素だけで、2つのテクスチャの違いを数える（余白の塗り広げを除く）。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,A1,B1=a[0],a[1],a[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
mw=mesh.matrix_world
ia=bpy.data.images.load(A1); W,H=ia.size
A=np.array(ia.pixels[:],dtype=np.float32).reshape(H,W,4)[:,:,:3]
ib=bpy.data.images.load(B1)
Bx=np.array(ib.pixels[:],dtype=np.float32).reshape(ib.size[1],ib.size[0],4)[:,:,:3]
uvl=me.uv_layers.active.data; me.calc_loop_triangles()
used=np.zeros((H,W),bool)
for t in me.loop_triangles:
    uv=np.array([uvl[li].uv for li in t.loops],float)
    xs=uv[:,0]*W; ys=uv[:,1]*H
    x0=max(0,int(np.floor(xs.min()))); x1=min(W-1,int(np.ceil(xs.max())))
    y0=max(0,int(np.floor(ys.min()))); y1=min(H-1,int(np.ceil(ys.max())))
    if x1<x0 or y1<y0 or (x1-x0)>500 or (y1-y0)>500: continue
    gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
    dd=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
    if abs(dd)<1e-12: continue
    l1=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/dd
    l2=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/dd
    l3=1-l1-l2
    used[y0:y1+1,x0:x1+1] |= (l1>=0)&(l2>=0)&(l3>=0)
d=(np.abs(A-Bx).sum(2)>0.02)&used
print("UC 面が使う画素 %d、そのうち違う画素 %d（%.4f%%）"%(int(used.sum()),int(d.sum()),100*d.sum()/max(1,used.sum())))
ys,xs=np.where(d)
if len(ys):
    cell={}
    for y,x in zip(ys,xs): cell[(y//64,x//64)]=cell.get((y//64,x//64),0)+1
    for (cy,cx),n in sorted(cell.items(),key=lambda kv:-kv[1])[:8]:
        print("UC   %5d画素 UV(%.3f,%.3f)付近"%(n,(cx*64+32)/W,(cy*64+32)/H))
