# 面ごとの平均色で部位を分け、それぞれが高さ・前後のどこにあるかを出す
import bpy,sys
import numpy as np
SRC=sys.argv[sys.argv.index("--")+1]
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
def cls(c):
    r,g,b=float(c[0]),float(c[1]),float(c[2])
    mx,mn=max(r,g,b),min(r,g,b)
    if mx<0.30: return "黒っぽい"
    if mx-mn<0.08: return "白/灰"
    if r>0.55 and g<0.45*r and b<0.55*r: return "赤"
    if b>0.35 and b>r*1.15 and b>g*1.05: return "青"
    if r>0.65 and g>0.45 and b<0.45 and g<0.85*r+0.15 and (r-b)>0.30 and g>0.55*r: return "黄"
    if r>0.75 and g>0.60 and b>0.50: return "肌"
    if r>0.40 and 0.25*r<g<0.75*r and b<0.5*r: return "茶(髪)"
    return "その他"
acc={}
for f in mesh.polygons:
    c=MW@f.center
    uu=[uvl[li].uv for li in f.loop_indices]
    cu=(sum(x.x for x in uu)/len(uu), sum(x.y for x in uu)/len(uu))
    px=int(cu[0]*W)%W; py=int(cu[1]*H)%H
    k=cls(A[py,px,:3])
    acc.setdefault(k,[]).append((c.x,c.y,c.z))
for k,v in sorted(acc.items(), key=lambda t:-len(t[1])):
    P=np.array(v)
    print("PS %-8s %5d面  x %.2f〜%.2f  y %.2f〜%.2f  z %.2f〜%.2f"%(k,len(P),P[:,0].min(),P[:,0].max(),P[:,1].min(),P[:,1].max(),P[:,2].min(),P[:,2].max()))
