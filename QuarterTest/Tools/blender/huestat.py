# 指定した箱の中の画素について、色相と鮮やかさの分布を出す
import bpy,sys,colorsys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC=a[0]; BOX=[float(x) for x in a[1].split(',')]
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
xlo,xhi,ylo,yhi,zlo,zhi=BOX
rows=[]
for f in mesh.polygons:
    c=MW@f.center
    if not (xlo-0.05<=c.x<=xhi+0.05 and ylo-0.05<=c.y<=yhi+0.05 and zlo-0.05<=c.z<=zhi+0.05): continue
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
                if not (xlo<=p.x<=xhi and ylo<=p.y<=yhi and zlo<=p.z<=zhi): continue
                r,g,b=[float(v) for v in A[py,px,:3]]
                h,s,v=colorsys.rgb_to_hsv(r,g,b)
                hh = h-1.0 if h>0.5 else h        # 赤は 0 をまたぐので負の値で表す
                rows.append((hh,s,v))
R=np.array(rows)
print("HS 画素 %d"%len(R))
for lo,hi in [(-0.05,-0.02),(-0.02,0.00),(0.00,0.02),(0.02,0.04),(0.04,0.06),(0.06,0.09),(0.09,0.20)]:
    m=(R[:,0]>=lo)&(R[:,0]<hi)
    if m.sum()==0: continue
    s=R[m,1]
    print("HS 色相%+.2f〜%+.2f  %6d画素  鮮やかさ 最小%.2f 25%%%.2f 中央%.2f 75%%%.2f 最大%.2f"%(
        lo,hi,int(m.sum()),s.min(),np.percentile(s,25),np.median(s),np.percentile(s,75),s.max()))
