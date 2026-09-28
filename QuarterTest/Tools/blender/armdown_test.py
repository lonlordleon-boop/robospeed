# 1つの glb の中で、上腕を体の方へ DEG 度下ろし（骨だけ回す）、前後で辺の伸びと、髪（暗い色）の頂点の動きを測る
import bpy,sys,math,colorsys,numpy as np,collections
from mathutils import Matrix, Quaternion, Vector
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]; DEG=float(a[1]) if len(a)>1 else 50
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
if arm.animation_data:
    for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
    arm.animation_data.action=None
for pb in arm.pose.bones: pb.matrix_basis=Matrix.Identity(4)
me=next(o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith('Icosphere')); m=me.data
def pos():
    bpy.context.view_layer.update(); dg=bpy.context.evaluated_depsgraph_get(); em=me.evaluated_get(dg).to_mesh()
    P=np.array([tuple(me.matrix_world@v.co) for v in em.vertices]); me.evaluated_get(dg).to_mesh_clear(); return P
P0=pos()
for s,sg in (('Left',1),('Right',-1)):
    pb=arm.pose.bones[s+'Arm']; h=pb.head.copy()
    q=Quaternion(Vector((0,1,0)), math.radians(DEG)*sg)   # 前後の軸まわりに回して下ろす
    pb.matrix=Matrix.Translation(h)@q.to_matrix().to_4x4()@Matrix.Translation(-h)@pb.matrix
P1=pos()
E=np.array([e.vertices[:] for e in m.edges]); L0=np.linalg.norm(P0[E[:,0]]-P0[E[:,1]],axis=1)+1e-9; L1=np.linalg.norm(P1[E[:,0]]-P1[E[:,1]],axis=1)
r=L1/L0; bad=np.nonzero((r>1.5)&(L1>0.004))[0]
gi={g.index:g.name for g in me.vertex_groups}
print("AT 腕を %.0f 度下ろした  辺が1.5倍超・4mm以上に伸びた %d 本"%(DEG,len(bad)))
cells=collections.Counter(); ex={}
for i in bad:
    p=P0[E[i,0]]; k=(round(p[0]/0.05)*0.05, round(p[2]/0.05)*0.05, 'front' if p[1]<0 else 'back'); cells[k]+=1
    ex.setdefault(k,(r[i],L1[i],{gi[e.group]:round(e.weight,2) for e in m.vertices[E[i,0]].groups if e.weight>0.05},{gi[e.group]:round(e.weight,2) for e in m.vertices[E[i,1]].groups if e.weight>0.05}))
for k,n in cells.most_common(10):
    rr,lb,w0,w1=ex[k]; print("AT x%.2f z%.2f %s: %d本  例 %.1f倍 %.1fcm %s | %s"%(k[0],k[1],k[2],n,rr,lb*100,w0,w1))
# 髪（暗い色）で 2mm 以上動いた頂点
img=next(n.image for n in me.active_material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
W,H=img.size; px=np.array(img.pixels[:],np.float32).reshape(H,W,4); uvl=m.uv_layers.active.data; vuv={}
for l in m.loops: vuv.setdefault(l.vertex_index,uvl[l.index].uv[:])
mv=np.linalg.norm(P1-P0,axis=1); hm=[]
for v in m.vertices:
    uv=vuv.get(v.index)
    if uv is None or P0[v.index][2]<0.55: continue
    c=px[int(np.clip(uv[1],0,.9999)*H),int(np.clip(uv[0],0,.9999)*W),:3]
    if max(c)<0.2 and mv[v.index]>0.002: hm.append(v.index)
print("AT 暗い色（髪）で 2mm 以上動いた頂点 %d"%len(hm))
if hm:
    Q=P0[hm]; print("AT   その範囲 x %.3f〜%.3f z %.3f〜%.3f  最大 %.1fcm"%(Q[:,0].min(),Q[:,0].max(),Q[:,2].min(),Q[:,2].max(),mv[hm].max()*100))
