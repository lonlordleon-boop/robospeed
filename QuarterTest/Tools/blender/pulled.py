# 頭の重みを持つ頂点（Head ≥ HMIN）のうち、動くと頭から見た位置がずれるもの（＝ほかの骨に引っ張られる）を探す。
# 同じ位置でつながるかたまりにまとめ、大きさ・場所・引っ張る骨・ずれの最大を出す
import bpy, sys, numpy as np, collections
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC = a[0]; HMIN = float(a[1]); DMIN = float(a[2])
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
gi = {g.index: g.name for g in me.vertex_groups}
HW = np.zeros(len(m.vertices)); OTH = [''] * len(m.vertices)
for v in m.vertices:
    for e in v.groups:
        if gi[e.group] == 'Head': HW[v.index] = e.weight
    o = [(e.weight, gi[e.group]) for e in v.groups if gi[e.group] != 'Head']
    OTH[v.index] = max(o)[1] if o else ''
cand = np.nonzero((HW >= HMIN) & (HW < 0.995))[0]
def pos():
    dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
    P = np.array([tuple(me.matrix_world @ v.co) for v in em.vertices]); me.evaluated_get(dg).to_mesh_clear(); return P
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update(); P0 = pos()
hb = arm.pose.bones['Head']; R0 = (arm.matrix_world @ hb.matrix)
L0 = np.array([tuple(R0.inverted() @ __import__('mathutils').Vector(P0[i])) for i in cand])
dmax = np.zeros(len(cand)); clipmax = [''] * len(cand)
for act in bpy.data.actions:
    arm.animation_data.action = act; f0, f1 = map(int, act.frame_range)
    for f in range(f0, f1 + 1, 2):
        bpy.context.scene.frame_set(f); P = pos(); R = (arm.matrix_world @ hb.matrix)
        Ri = R.inverted()
        L = np.array([tuple(Ri @ __import__('mathutils').Vector(P[i])) for i in cand])
        d = np.linalg.norm((L - L0), axis=1) * 0.01 * 100  # 骨の空間（cm）→ そのまま cm
        upd = d > dmax
        for k in np.nonzero(upd)[0]: clipmax[k] = act.name
        dmax = np.maximum(dmax, d)
sel = [k for k in range(len(cand)) if dmax[k] > DMIN]
# 同じ位置でつながるかたまり
key = {}
for v in m.vertices: key.setdefault(tuple(np.round(np.array(v.co), 5)), []).append(v.index)
par = {}
def find(x):
    while par.get(x, x) != x: par[x] = par.get(par[x], par[x]); x = par[x]
    return x
selv = set(int(cand[k]) for k in sel)
canon = {}
for vs in key.values():
    for v in vs: canon[v] = vs[0]
for e in m.edges:
    a0, b0 = e.vertices
    if a0 in selv and b0 in selv:
        ra, rb = find(canon[a0]), find(canon[b0])
        if ra != rb: par[ra] = rb
groups = collections.defaultdict(list)
for k in sel: groups[find(canon[int(cand[k])])].append(k)
out = sorted(groups.values(), key=lambda g: -max(dmax[k] for k in g))
print("PL 候補 %d 頂点 / ずれ > %.1f cm: %d 頂点, かたまり %d" % (len(cand), DMIN, len(sel), len(out)))
for g in out[:15]:
    ps = P0[[cand[k] for k in g]]
    oth = collections.Counter(OTH[cand[k]] for k in g).most_common(2)
    cl = collections.Counter(clipmax[k] for k in g).most_common(1)
    print("PL %3d 頂点 ずれ最大 %.1fcm  x %.3f〜%.3f y %.3f〜%.3f z %.3f〜%.3f  頭の重み %.2f〜%.2f  ほかの骨 %s  %s" % (len(g), max(dmax[k] for k in g), ps[:,0].min(), ps[:,0].max(), ps[:,1].min(), ps[:,1].max(), ps[:,2].min(), ps[:,2].max(), min(HW[cand[k]] for k in g), max(HW[cand[k]] for k in g), oth, cl))
