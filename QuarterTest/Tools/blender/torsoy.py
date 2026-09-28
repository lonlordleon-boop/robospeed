# 高さごとに、真ん中（|x|<XW）の明るい色（服・肌）の頂点の前後（y）の最小・最大・真ん中を出す。髪（暗い色）は外す
import bpy,sys,colorsys,numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]; XW=float(a[1]) if len(a)>1 else 0.04
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
me=next(o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith('Icosphere')); m=me.data
img=next(n.image for n in me.active_material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
W,H=img.size; px=np.array(img.pixels[:],np.float32).reshape(H,W,4); uvl=m.uv_layers.active.data; vuv={}
for l in m.loops: vuv.setdefault(l.vertex_index,uvl[l.index].uv[:])
P=np.array([tuple(me.matrix_world@v.co) for v in m.vertices])
ok=np.zeros(len(P),bool)
for v in m.vertices:
    uv=vuv.get(v.index)
    if uv is None: continue
    c=px[int(np.clip(uv[1],0,.9999)*H),int(np.clip(uv[0],0,.9999)*W),:3]
    ok[v.index]=max(c)>0.55
for z in np.arange(0.30,0.92,0.04):
    s=ok&(np.abs(P[:,0])<XW)&(np.abs(P[:,2]-z)<0.01)
    if s.sum()<3: print("TY z%.2f 少ない"%z); continue
    y=P[s,1]; print("TY z%.2f  前 %6.1f  後 %6.1f  真ん中 %6.1f cm  (%d 頂点)"%(z,y.min()*100,y.max()*100,(y.min()+y.max())*50,s.sum()))
