# 髪（暗い色：明るさ0.25未満）の頂点を高さの帯ごとに分け、主な骨の数と、腕・肩の重みを持つ頂点の数を出す
import bpy,sys,colorsys,numpy as np,collections
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
me=next(o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith('Icosphere')); m=me.data
img=next(n.image for n in me.active_material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
W,H=img.size; px=np.array(img.pixels[:],np.float32).reshape(H,W,4)
uvl=m.uv_layers.active.data; vuv={}
for l in m.loops: vuv.setdefault(l.vertex_index,uvl[l.index].uv[:])
gi={g.index:g.name for g in me.vertex_groups}
bands=collections.defaultdict(collections.Counter); armc=collections.Counter(); tot=collections.Counter()
for v in m.vertices:
    uv=vuv.get(v.index)
    if uv is None: continue
    c=px[int(np.clip(uv[1],0,.9999)*H),int(np.clip(uv[0],0,.9999)*W),:3]
    if max(c)>0.25: continue
    z=(me.matrix_world@v.co).z; b=round(np.floor(z*20)/20,2)
    g=max(v.groups,key=lambda e:e.weight,default=None)
    bands[b][gi[g.group] if g else '-']+=1; tot[b]+=1
    if sum(e.weight for e in v.groups if any(k in gi[e.group] for k in ('Arm','Shoulder','Hand')))>0.05: armc[b]+=1
for b in sorted(bands,reverse=True):
    print("HW z%.2f 頂点%5d 腕・肩あり%5d  主な骨 %s"%(b,tot[b],armc[b],bands[b].most_common(4)))
