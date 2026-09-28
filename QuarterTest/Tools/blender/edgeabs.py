# 箱の中で伸びる辺（全クリップの最大）の両端の頂点：位置・明るさ・重みの上位
import bpy, sys, colorsys, numpy as np, collections
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC = a[0]; TH = float(a[1]); BOX = tuple(map(float, a[2].split(','))); NSHOW = int(a[3]) if len(a) > 3 else 30
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
vuv = {}
for l in m.loops: vuv.setdefault(l.vertex_index, uvl[l.index].uv[:])
def val(i):
    uv = vuv[i]; c = px[int(np.clip(uv[1],0,.9999)*H_), int(np.clip(uv[0],0,.9999)*W_), :3]; return colorsys.rgb_to_hsv(*c)[2]
tracks = [(t.name, t.strips[0].action) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
def pos():
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
    P = np.array([tuple(me.matrix_world @ v.co) for v in em.vertices]); me.evaluated_get(dg).to_mesh_clear(); return P
P0 = pos(); E = np.array([e.vertices[:] for e in m.edges])
c = (P0[E[:,0]] + P0[E[:,1]]) / 2
inb = (c[:,0]>=BOX[0])&(c[:,0]<=BOX[1])&(c[:,1]>=BOX[2])&(c[:,1]<=BOX[3])&(c[:,2]>=BOX[4])&(c[:,2]<=BOX[5])
E = E[inb]; L0 = np.linalg.norm(P0[E[:,0]]-P0[E[:,1]],axis=1)+1e-9
mx = np.zeros(len(E)); who = ['']*len(E)
for nm, act in tracks:
    arm.animation_data.action = act; f0, f1 = map(int, act.frame_range)
    for f in range(f0, f1+1):
        bpy.context.scene.frame_set(f); P = pos(); r = np.linalg.norm(P[E[:,0]]-P[E[:,1]],axis=1)-L0
        up = r > mx; mx = np.where(up, r, mx)
        for i in np.nonzero(up)[0]: who[i] = "%s%d" % (nm, f)
gi = {g.index: g.name for g in me.vertex_groups}
def wt(i): return " ".join("%s%.2f" % (n.replace('Left','L').replace('Right','R'), w) for w, n in sorted([(e.weight, gi[e.group]) for e in m.vertices[i].groups], reverse=True)[:3])
sel = np.nonzero(mx > TH)[0]
print("ES 伸びる辺", len(sel), "/", len(E))
# 頂点ごとにまとめる：両端の組の種類
kinds = collections.Counter()
for i in sel:
    a_, b_ = E[i]
    def dom(x): return max([(e.weight, gi[e.group]) for e in m.vertices[x].groups], default=(0,'-'))[1]
    kinds[(("暗" if val(a_)<0.4 else "明")+dom(a_), ("暗" if val(b_)<0.4 else "明")+dom(b_))] += 1
for k, n in kinds.most_common(25): print("ES", n, k)
for i in sel[np.argsort(-mx[sel])][:NSHOW]:
    a_, b_ = E[i]
    print("ES +%5.3fm %-10s A(%.3f,%.3f,%.3f) v%.2f [%s] | B(%.3f,%.3f,%.3f) v%.2f [%s]" % (mx[i], who[i], *P0[a_], val(a_), wt(a_), *P0[b_], val(b_), wt(b_)))
