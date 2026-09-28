# 決まった高さに色の帯を焼いて、画面のどこに来るかを確かめる（位置合わせ用）
import bpy,sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,OUT=a[0],a[1]
BANDS=[(float(x.split(':')[0]), tuple(float(v) for v in x.split(':')[1].split(','))) for x in a[2].split(';')]
T=float(a[3])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o,do_unlink=True)
me=next(o for o in bpy.data.objects if o.type=='MESH'); mesh=me.data
uvl=mesh.uv_layers.active.data
img=None
for m in mesh.materials:
    if not m or not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE' and n.image: img=n.image; break
W,H=img.size; A=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
MW=me.matrix_world
zlo=min(b[0] for b in BANDS)-T; zhi=max(b[0] for b in BANDS)+T
cnt=0
for f in mesh.polygons:
    c=MW@f.center
    if c.z<zlo-0.05 or c.z>zhi+0.05 or c.y>0: continue
    vs=[mesh.vertices[v].co for v in f.vertices]; uv=[uvl[li].uv for li in f.loop_indices]
    for i in range(1,len(vs)-1):
        tri=[vs[0],vs[i],vs[i+1]]; tuv=[uv[0],uv[i],uv[i+1]]
        xs=[t.x*W for t in tuv]; ys=[t.y*H for t in tuv]
        x0=max(0,int(min(xs))-1); x1=min(W-1,int(max(xs))+1)
        y0=max(0,int(min(ys))-1); y1=min(H-1,int(max(ys))+1)
        den=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(den)<1e-12 or x1<x0 or y1<y0: continue
        for py in range(y0,y1+1):
            for px in range(x0,x1+1):
                gx,gy=px+0.5,py+0.5
                l1=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/den
                l2=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/den
                l3=1.0-l1-l2
                if l1<-0.05 or l2<-0.05 or l3<-0.05: continue
                p=MW@(tri[0]*l1+tri[1]*l2+tri[2]*l3)
                for z0,col in BANDS:
                    if abs(p.z-z0)<T:
                        A[py,px,:3]=col; cnt+=1; break
print("ZB 塗った画素",cnt)
o=bpy.data.images.new("zb",W,H,alpha=True); o.pixels=A.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("ZB",OUT)
