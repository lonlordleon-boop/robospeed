# 伸びる辺を、クリップごと・主な骨の組ごとに数える
import bpy, sys, numpy as np, collections
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC = a[0]; TH = float(a[1]) if len(a) > 1 else 1.5
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
E = np.array([e.vertices[:] for e in m.edges])
def pos():
    dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
    P = np.array([tuple(me.matrix_world @ v.co) for v in em.vertices]); me.evaluated_get(dg).to_mesh_clear(); return P
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
P0 = pos(); L0 = np.linalg.norm(P0[E[:, 0]] - P0[E[:, 1]], axis=1) + 1e-9
gi = {g.index: g.name for g in me.vertex_groups}
dom = []
for v in m.vertices:
    g = max(v.groups, key=lambda e: e.weight, default=None); dom.append(gi[g.group] if g else '-')
for act in bpy.data.actions:
    arm.animation_data.action = act; mx = np.ones(len(E)); worst = (0, 0)
    f0, f1 = map(int, act.frame_range)
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f); P = pos()
        r = np.linalg.norm(P[E[:, 0]] - P[E[:, 1]], axis=1) / L0
        n = int((r > TH).sum())
        if n > worst[1]: worst = (f, n)
        mx = np.maximum(mx, r)
    bad = np.nonzero(mx > TH)[0]
    c = collections.Counter(tuple(sorted((dom[E[i,0]], dom[E[i,1]]))) for i in bad)
    print("S2 %s 辺 %d 本  最大 %.2f倍  一番多いコマ %d（%d 本）" % (act.name, len(bad), mx.max(), worst[0], worst[1]))
    for k, v in c.most_common(8): print("S2    ", k, v)
