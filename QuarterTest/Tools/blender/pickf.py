# 描いた絵の画素の位置から、そこに写る頂点を探す（shot.py と同じカメラ）
import bpy, sys, math, colorsys, numpy as np
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view
a = sys.argv[sys.argv.index("--")+1:]; SRC, CLIP, FR = a[0], a[1], int(a[2]); AZ, EL, SCALE, CZ, CX = map(float, a[3:8]); PXX, PXY, R = map(float, a[8:11])
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
vuv = {}
for l in m.loops: vuv.setdefault(l.vertex_index, uvl[l.index].uv[:])
gi = {g.index: g.name for g in me.vertex_groups}
P0 = [me.matrix_world @ v.co for v in m.vertices]
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
act = next(x for x in bpy.data.actions if x.name.startswith(CLIP)); arm.animation_data.action = act
sc = bpy.context.scene; sc.frame_set(FR); bpy.context.view_layer.update()
CW = 420; CH = int(CW*1.6); sc.render.resolution_x = CW; sc.render.resolution_y = CH
cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cd.ortho_scale = SCALE
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
hp = arm.matrix_world @ arm.pose.bones['Hips'].head; C = Vector((hp.x + CX, hp.y, CZ))
ar = math.radians(AZ); el = math.radians(EL)
cam.location = (C.x + 5*math.sin(ar)*math.cos(el), C.y - 5*math.cos(ar)*math.cos(el), C.z + 5*math.sin(el))
cam.rotation_euler = (C - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler(); bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
from mathutils.bvhtree import BVHTree
import bmesh
bm = bmesh.new(); bm.from_mesh(em); bm.transform(me.matrix_world); bm.faces.ensure_lookup_table(); tree = BVHTree.FromBMesh(bm)
fwd = (C - Vector(cam.location)).normalized(); rgt = fwd.cross(Vector((0,0,1))).normalized(); up = rgt.cross(fwd)
pxs = SCALE / CH
seen = set()
for dx in range(-int(R), int(R)+1, 3):
  for dy in range(-int(R), int(R)+1, 3):
    o = Vector(cam.location) + rgt * ((PXX + dx - CW/2) * pxs) + up * ((CH/2 - (PXY + dy)) * pxs)
    hit = tree.ray_cast(o, fwd, 20)
    if hit[0] is None or hit[2] in seen: continue
    seen.add(hit[2]); f = m.polygons[hit[2]]
    uv = np.mean([uvl[li].uv[:] for li in f.loop_indices], 0); col = px[int(np.clip(uv[1],0,.9999)*H_), int(np.clip(uv[0],0,.9999)*W_), :3]
    PP = [bm.faces[hit[2]].verts[k].co for k in range(len(f.vertices))]
    ln = max((PP[k]-PP[(k+1)%len(PP)]).length for k in range(len(PP)))
    ln0 = max((P0[f.vertices[k]]-P0[f.vertices[(k+1)%len(PP)]]).length for k in range(len(PP)))
    print("FC f%d d(%d,%d) v%.2f 辺 %.3f→%.3f" % (hit[2], dx, dy, colorsys.rgb_to_hsv(*col)[2], ln0, ln))
    for vi in f.vertices:
        wt = " ".join("%s%.2f" % (gi[e.group].replace('Left','L').replace('Right','R'), e.weight) for e in sorted(m.vertices[vi].groups, key=lambda e: -e.weight)[:3])
        print("   #%d rest%s [%s]" % (vi, tuple(round(t,3) for t in P0[vi]), wt))
