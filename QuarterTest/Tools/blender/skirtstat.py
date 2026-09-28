# 明るい色（肌でない：彩度<0.12 か青い花柄）の頂点を、高さの帯ごとに主な骨で数え、脚の骨の重みの平均を出す
import bpy,sys,colorsys,numpy as np,collections
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
me=next(o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith('Icosphere')); m=me.data
img=next(n.image for n in me.active_material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
W,H=img.size; px=np.array(img.pixels[:],np.float32).reshape(H,W,4); uvl=m.uv_layers.active.data; vuv={}
for l in m.loops: vuv.setdefault(l.vertex_index,uvl[l.index].uv[:])
gi={g.index:g.name for g in me.vertex_groups}
B=collections.defaultdict(collections.Counter); LW=collections.defaultdict(list)
for v in m.vertices:
    p=me.matrix_world@v.co
    if not 0.30<p.z<0.80 or abs(p.x)>0.30: continue
    uv=vuv.get(v.index); c=px[int(np.clip(uv[1],0,.9999)*H),int(np.clip(uv[0],0,.9999)*W),:3]; h,s,val=colorsys.rgb_to_hsv(*c)
    cloth=(val>0.6 and s<0.12) or (190/360<h<260/360 and s>0.12 and val>0.4)
    if not cloth: continue
    b=round(np.floor(p.z*20)/20,2); g=max(v.groups,key=lambda e:e.weight)
    B[b][gi[g.group]]+=1; LW[b].append(sum(e.weight for e in v.groups if 'Leg' in gi[e.group]))
for b in sorted(B,reverse=True): print("SK z%.2f 頂点%4d 脚の重み平均 %.2f 主な骨 %s"%(b,sum(B[b].values()),np.mean(LW[b]),B[b].most_common(4)))
