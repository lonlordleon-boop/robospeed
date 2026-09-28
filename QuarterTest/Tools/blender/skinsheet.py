# 頭のまわりの「房の薄い板（裏 6mm 以内に反対向きの面）」のうち、肌色の絵が貼られた面を数えて赤で描く。髪の色は問わない。
# 引数: glb out.png
import bpy, bmesh, sys, math, os, colorsys, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
for o in bpy.data.objects:
    if o.type == 'ARMATURE' and o.animation_data:
        for tr in o.animation_data.nla_tracks: tr.mute = True
        o.animation_data.action = None
        for pb in o.pose.bones: pb.matrix_basis.identity()
bpy.context.view_layer.update()
me = next(o for o in bpy.data.objects if o.type == 'MESH'); m = me.data; MW = me.matrix_world
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
P = np.array([tuple(MW @ v.co) for v in m.vertices]); top = P[:, 2].max(); bot = P[:, 2].min(); Hh = top - bot; sc = Hh / 1.3
bm = bmesh.new(); bm.from_mesh(m); bm.transform(MW); bm.faces.ensure_lookup_table(); tree = BVHTree.FromBMesh(bm)
def col(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0); return colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])
nsheet = nskin = 0; red = []
for f in bm.faces:
    c = f.calc_center_median()
    if c.z < top - 0.33 * sc: continue   # 頭（上から 33cm 相当）
    n = f.normal.normalized(); h = tree.ray_cast(c - n * 0.0003 * sc, -n, 0.006 * sc)
    if h[0] is None or h[2] == f.index or bm.faces[h[2]].normal.normalized().dot(n) > -0.5: continue
    nsheet += 1
    hh, s, v = col(m.polygons[f.index])
    if v >= 0.75 and s < 0.3 and (hh < 0.14 or hh > 0.95 or s < 0.08): nskin += 1; red.append(f.index)
print("SS %s 薄い板 %d・うち肌色 %d" % (os.path.basename(SRC), nsheet, nskin))
rm = bpy.data.materials.new("red"); rm.diffuse_color = (1, 0, 0, 1); m.materials.append(rm); ri = len(m.materials) - 1
for fi in red: m.polygons[fi].material_index = ri
scn = bpy.context.scene; scn.render.engine = 'BLENDER_WORKBENCH'; scn.display.shading.light = 'FLAT'; scn.display.shading.color_type = 'TEXTURE'
scn.display.shading.show_backface_culling = False; scn.world = bpy.data.worlds.new("w"); scn.world.use_nodes = False; scn.world.color = (1, 1, 1)
CW = 400; scn.render.resolution_x = CW; scn.render.resolution_y = CW
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cd.ortho_scale = 0.36 * sc; cam = bpy.data.objects.new("c", cd); scn.collection.objects.link(cam); scn.camera = cam
C = Vector((0, 0, top - 0.17 * sc)); tiles = []; tmp = os.path.join(os.path.dirname(OUT), "_ss"); os.makedirs(tmp, exist_ok=True)
for az in (0, 40, 90, -40, -90):
    ar_ = math.radians(az); cam.location = (C.x + 5*math.sin(ar_), C.y - 5*math.cos(ar_), C.z); cam.rotation_euler = (C - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(tmp, "p%d.png" % len(tiles)); scn.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
buf = np.ones((CW, CW * len(tiles), 4), np.float32)
for i, p in enumerate(tiles):
    im = bpy.data.images.load(p); buf[:, i*CW:(i+1)*CW] = np.array(im.pixels[:], np.float32).reshape(CW, CW, 4)
shi = bpy.data.images.new("s", CW * len(tiles), CW); shi.pixels = buf.ravel(); shi.filepath_raw = OUT; shi.file_format = 'PNG'; shi.save(); print("SS", OUT)
