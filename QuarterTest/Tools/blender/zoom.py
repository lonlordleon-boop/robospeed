# 指定のクリップ・コマで、首と肩のあたりを前・斜め・後ろから拡大して描く。伸びる辺の頂点を赤い点で重ねる
import bpy, sys, math, os, numpy as np
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT, CLIP, FR = a[0], a[1], a[2], int(a[3])
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
act = next(x for x in bpy.data.actions if x.name.startswith(CLIP)); arm.animation_data.action = act
sc = bpy.context.scene; sc.frame_set(FR)
sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = False; sc.world.color = (1, 1, 1)
CW = 420; sc.render.resolution_x = CW; sc.render.resolution_y = CW
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cd.ortho_scale = 0.42
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
me = next(o for o in bpy.data.objects if o.type == 'MESH')
arm_hips = arm.pose.bones['Hips']
dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
P = np.array([tuple(me.matrix_world @ v.co) for v in em.vertices])
nk = arm.matrix_world @ arm.pose.bones[a[4] if len(a)>4 else 'neck'].head
C = Vector((nk.x, nk.y, nk.z + 0.03))
tiles = []; tmp = os.path.join(os.path.dirname(OUT), "_nz"); os.makedirs(tmp, exist_ok=True)
for az in ((0, 90, 135, 180) if len(a)>5 else (0, 45, 180)):
    ar = math.radians(az); R = 5
    cam.location = (C.x + R*math.sin(ar), C.y - R*math.cos(ar), C.z)
    cam.rotation_euler = (C - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(tmp, "n%d.png" % az); sc.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
buf = np.ones((CW, CW*len(tiles), 4), np.float32)
for i, p in enumerate(tiles):
    im = bpy.data.images.load(p); buf[:, i*CW:(i+1)*CW] = np.array(im.pixels[:], np.float32).reshape(CW, CW, 4)
sh = bpy.data.images.new("s", CW*len(tiles), CW); sh.pixels = buf.ravel(); sh.filepath_raw = OUT; sh.file_format = 'PNG'; sh.save()
