# -*- coding: utf-8 -*-
"""頭のうち肌色に塗られている面が、どこに分布しているかを表にする（耳の外にはみ出している範囲を掴む）。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,TEX=a[0],a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
mw=mesh.matrix_world
hp=mw.inverted()@(arm.matrix_world@arm.pose.bones['Head'].head)
neckz=(arm.matrix_world@arm.pose.bones['neck'].head).z
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
rows=[]
for f in me.polygons:
    c=mw@f.center
    if c.z<neckz: continue
    uv=np.array([uvl[li].uv for li in f.loop_indices])
    col=np.mean([px[int(np.clip(u[1],0,.9999)*H),int(np.clip(u[0],0,.9999)*W),:3] for u in uv],0)
    r,g,b=col
    k = 1 if (r>0.68 and g>0.42 and b>0.32 and g<r*0.99 and b<g*1.08) else (2 if (r>0.28 and g<r*0.75 and b<r*0.55) else 0)
    rows.append((c.x,c.y,c.z,k))
R=np.array(rows)
print("SM 頭の面 %d（肌%d 髪%d その他%d）"%(len(R),(R[:,3]==1).sum(),(R[:,3]==2).sum(),(R[:,3]==0).sum()))
side=np.abs(R[:,0])>0.13
print("SM 横（|x|>0.13）の面 %d：肌%d 髪%d"%(side.sum(),((R[:,3]==1)&side).sum(),((R[:,3]==2)&side).sum()))
sk=R[(R[:,3]==1)&side]
if len(sk):
    print("SM   横の肌の面 y %.3f..%.3f  z %.3f..%.3f"%(sk[:,1].min(),sk[:,1].max(),sk[:,2].min(),sk[:,2].max()))
    yb=[-0.30,-0.22,-0.16,-0.10,-0.04,0.05,0.30]; zb=[0.5,0.62,0.68,0.72,0.78,0.9,1.3]
    print("SM   z＼y  " + " ".join("%12s"%("%.2f..%.2f"%(yb[j],yb[j+1])) for j in range(len(yb)-1)))
    for i in range(len(zb)-1):
        row=[]
        for j in range(len(yb)-1):
            m=(sk[:,2]>=zb[i])&(sk[:,2]<zb[i+1])&(sk[:,1]>=yb[j])&(sk[:,1]<yb[j+1]); row.append(int(m.sum()))
        print("SM   %.2f..%.2f " % (zb[i],zb[i+1]) + " ".join("%12d"%x for x in row))
