# -*- coding: utf-8 -*-
"""腕の重みで動いてしまう髪の房を消す（「右腕に引っ張られている髪の毛がまだ１本ある」）。
   髪の色（色相 12〜45度・彩度 0.45 以上）の面のうち、腕（肩・上腕・前腕・手）の重みが WMIN 以上の頂点に触れ、
   高さ ZMIN より上・左右 XMAX より外（右は x < XMAX）の面を種にして、腕の重みを少しでも持つ髪の色の面へ広げる。
   show: 緑に塗って4方向から描くだけ。cut: 消して書き出す（骨・重み・動き・絵はそのまま）
   実行: blender -b --factory-startup -P strandcut.py -- 入力.glb show|cut 出力 [WMIN 0.3] [ZMIN 0.60] [XMAX -0.12]"""
import bpy, bmesh, sys, colorsys, math, os, numpy as np
from mathutils import Vector, Matrix
a = sys.argv[sys.argv.index("--")+1:]
SRC, MODE, OUT = a[0], a[1], a[2]
WMIN = float(a[3]) if len(a) > 3 else 0.3
ZMIN = float(a[4]) if len(a) > 4 else 0.60
XMAX = float(a[5]) if len(a) > 5 else -0.12
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH'); m = me.data
tracks = [(t.name, t.strips[0].action, int(t.strips[0].frame_start)) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
arm.animation_data.action = None
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
uvl = m.uv_layers.active.data; MW = me.matrix_world
gi = {g.index: g.name for g in me.vertex_groups}
AW = np.zeros(len(m.vertices))
for v in m.vertices:
    AW[v.index] = sum(e.weight for e in v.groups if any(k in gi[e.group] for k in ('Arm', 'Shoulder', 'Hand')))
P = np.array([tuple(MW @ v.co) for v in m.vertices])
def hairy(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    c = px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
    h, s, val = colorsys.rgb_to_hsv(*c)
    return 12/360 <= h <= 45/360 and s >= 0.45
HF = [hairy(p) for p in m.polygons]
key = {}
for v in m.vertices: key.setdefault(tuple(np.round(np.array(v.co), 5)), []).append(v.index)
canon = {}
for vs in key.values():
    for v in vs: canon[v] = vs[0]
vf = {}
for p in m.polygons:
    for v in p.vertices: vf.setdefault(canon[v], []).append(p.index)
seed = [p.index for p in m.polygons if HF[p.index]
        and max(AW[v] for v in p.vertices) >= WMIN
        and min(P[v][2] for v in p.vertices) >= ZMIN and max(P[v][0] for v in p.vertices) <= XMAX]
sel = set(seed); stack = list(seed)
while stack:
    f = stack.pop()
    for v in m.polygons[f].vertices:
        for g in vf[canon[v]]:
            if g not in sel and HF[g] and max(AW[w] for w in m.polygons[g].vertices) > 0.02:
                sel.add(g); stack.append(g)
vs = sorted(set(v for f in sel for v in m.polygons[f].vertices))
print("SC 種の面 %d  広げた面 %d  頂点 %d" % (len(seed), len(sel), len(vs)))
if vs:
    Q = P[vs]; print("SC 範囲 x %.3f〜%.3f y %.3f〜%.3f z %.3f〜%.3f  腕の重み %.2f〜%.2f" % (Q[:,0].min(), Q[:,0].max(), Q[:,1].min(), Q[:,1].max(), Q[:,2].min(), Q[:,2].max(), AW[vs].min(), AW[vs].max()))
if MODE == 'show':
    ca = m.color_attributes.new("c", 'BYTE_COLOR', 'CORNER')
    for p in m.polygons:
        for li in p.loop_indices:
            uv = uvl[li].uv
            c = px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3]
            ca.data[li].color = (0.0, 1.0, 0.0, 1.0) if p.index in sel else (float(c[0]), float(c[1]), float(c[2]), 1.0)
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'VERTEX'
    sc.view_settings.view_transform = 'Standard'
    sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = False; sc.world.color = (1, 1, 1)
    CW = 420; sc.render.resolution_x = CW; sc.render.resolution_y = CW
    cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cd.ortho_scale = 0.5
    cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
    C = Vector((-0.10, 0.0, 0.76))
    tiles = []; tmp = os.path.join(os.path.dirname(OUT), "_sc"); os.makedirs(tmp, exist_ok=True)
    for az in (0, 180, 270):
        ar = math.radians(az); cam.location = (C.x + 5*math.sin(ar), C.y - 5*math.cos(ar), C.z)
        cam.rotation_euler = (C - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
        p = os.path.join(tmp, "s%d.png" % az); sc.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
    buf = np.ones((CW, CW*len(tiles), 4), np.float32)
    for i, p in enumerate(tiles):
        im = bpy.data.images.load(p); buf[:, i*CW:(i+1)*CW] = np.array(im.pixels[:], np.float32).reshape(CW, CW, 4)
    sh = bpy.data.images.new("s", CW*len(tiles), CW); sh.pixels = buf.ravel(); sh.filepath_raw = OUT; sh.file_format = 'PNG'; sh.save()
else:
    bm = bmesh.new(); bm.from_mesh(m); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in sel], context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(m); bm.free(); m.update()
    want = ['Idle', 'Walk_Child', 'Run', 'Skip']
    tracks.sort(key=lambda t: want.index(t[0]) if t[0] in want else 99)
    for nm, act, fs in tracks:
        t2 = arm.animation_data.nla_tracks.new(); t2.name = nm; s2 = t2.strips.new(nm, fs, act); s2.name = nm
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
    print("SC 書き出し", OUT)
