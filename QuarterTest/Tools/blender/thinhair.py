# 素の姿勢で、髪の色の頂点のうち、ポニーテールの下（高さ ZHI より下・左右 XMIN より外）にあるものを探し、
# 同じ位置でつながったかたまりごとに大きさを報告する。cut を付けると、そのかたまりを消して書き出す
import bpy, bmesh, sys, colorsys, numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; ZHI = float(a[1]); XMIN = float(a[2]); CUT = len(a) > 3 and a[3] == 'cut'; OUT = a[4] if CUT else None
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
tracks = [(t.name, t.strips[0].action, int(t.strips[0].frame_start)) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data
MW = me.matrix_world
cand = set()
for p in m.polygons:
    ws = [MW @ m.vertices[v].co for v in p.vertices]
    if max(w.z for w in ws) > ZHI or min(w.z for w in ws) < 0.84 or max(w.x for w in ws) > -XMIN: continue
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    c = px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
    h, s, val = colorsys.rgb_to_hsv(*c)
    if 12/360 <= h <= 70/360 and s >= 0.3: cand.add(p.index)
print("TH 候補の面", len(cand))
if cand:
    ws = np.array([tuple(MW @ m.vertices[v].co) for i in cand for v in m.polygons[i].vertices])
    print("TH 範囲 x %.3f〜%.3f y %.3f〜%.3f z %.3f〜%.3f" % (ws[:,0].min(), ws[:,0].max(), ws[:,1].min(), ws[:,1].max(), ws[:,2].min(), ws[:,2].max()))
if CUT:
    bm = bmesh.new(); bm.from_mesh(m); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in cand], context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(m); bm.free(); m.update()
    want = ['Idle', 'Walk_Child', 'Run', 'Skip']
    tracks.sort(key=lambda t: want.index(t[0]) if t[0] in want else 99)
    for nm, act, fs in tracks:
        t2 = arm.animation_data.nla_tracks.new(); t2.name = nm; s2 = t2.strips.new(nm, fs, act); s2.name = nm
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
    print("TH 書き出し", OUT)
