# 肩のあたり（|x| X0〜X1、高さ Z0〜Z1）の頂点を、今の重み（腕あり／腕なし）と絵の明るさ・彩度で数える
import bpy,sys,colorsys,numpy as np,collections
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]; X0,X1,Z0,Z1=map(float,a[1:5])
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
me=next(o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith('Icosphere')); m=me.data
img=next(n.image for n in me.active_material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
W,H=img.size; px=np.array(img.pixels[:],np.float32).reshape(H,W,4); uvl=m.uv_layers.active.data; vuv={}
for l in m.loops: vuv.setdefault(l.vertex_index,uvl[l.index].uv[:])
gi={g.index:g.name for g in me.vertex_groups}
tab=collections.Counter()
for v in m.vertices:
    p=me.matrix_world@v.co
    if not (X0<=abs(p.x)<=X1 and Z0<=p.z<=Z1): continue
    uv=vuv.get(v.index); c=px[int(np.clip(uv[1],0,.9999)*H),int(np.clip(uv[0],0,.9999)*W),:3]; h,s,val=colorsys.rgb_to_hsv(*c)
    armw=sum(e.weight for e in v.groups if gi[e.group].endswith(('Arm','Shoulder','ForeArm')))
    tab[('腕あり' if armw>0.05 else '腕なし', '明%.1f'%(np.floor(val*10)/10), '彩<.25' if s<0.25 else '彩>=.25')]+=1
for k in sorted(tab): print("SC",k,tab[k])
