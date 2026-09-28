import bpy, sys, colorsys, numpy as np, collections
from mathutils import Vector
from mathutils.geometry import intersect_point_line
a = sys.argv[sys.argv.index("--")+1:]; SRC = a[0]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data:
    for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
    arm.animation_data.action = None
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
vuv = {}
for l in m.loops: vuv.setdefault(l.vertex_index, uvl[l.index].uv[:])
def bh(n): return arm.matrix_world @ arm.data.bones[n].head_local
LSEG = [(bh(s+'UpLeg'), bh(s+'Leg')) for s in ('Left','Right')] + [(bh(s+'Leg'), bh(s+'Foot')) for s in ('Left','Right')]
def legdist(p):
    pv = Vector(p); best = 9
    for h, t in LSEG:
        q, f = intersect_point_line(pv, h, t); f = min(1, max(0, f)); best = min(best, (pv-(h+(t-h)*f)).length)
    return best
D = collections.defaultdict(list)
for v in m.vertices:
    p = me.matrix_world @ v.co
    if not (0.2 < p.z < 0.6) or abs(p.x) > 0.3: continue
    uv = vuv[v.index]; c = px[int(np.clip(uv[1],0,.9999)*H_), int(np.clip(uv[0],0,.9999)*W_), :3]
    h,s,val = colorsys.rgb_to_hsv(*c)
    kind = 'skin' if (0.02 < h < 0.11 and 0.12 < s < 0.5 and val > 0.6) else ('dark' if val < 0.35 else 'cloth')
    D[(round(p.z*50)/50, kind)].append(legdist(p))
for k in sorted(D):
    d = np.array(D[k]); print("z%.2f %-5s n%4d  ld p5 %.3f p50 %.3f p95 %.3f" % (k[0], k[1], len(d), *np.percentile(d, [5,50,95])))
print("UpLeg", tuple(bh('LeftUpLeg')), "Leg", tuple(bh('LeftLeg')), "Hips", tuple(bh('Hips')))
