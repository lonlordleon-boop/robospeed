# -*- coding: utf-8 -*-
"""girl_v2〜v6 を Idle の先頭の姿勢で焼き込み、静止メッシュだけを横に並べた .blend を作る。
   骨も内部オブジェクトも残さないので、どの視点・どの表示モードでも普通に見える。
   実行: blender -b --factory-startup -P lineup.py -- 出力.blend 入力1.glb ..."""
import bpy, sys, os

a = sys.argv[sys.argv.index("--")+1:]
OUT, FILES = a[0], a[1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 24

made = []
for i, path in enumerate(FILES):
    label = os.path.splitext(os.path.basename(path))[0]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    added = [o for o in bpy.data.objects if o not in before]
    arm  = next((o for o in added if o.type == 'ARMATURE'), None)
    mesh = next((o for o in added if o.type == 'MESH' and o.name.startswith("char")), None)
    if arm is None or mesh is None:
        print("SKIP", label); continue

    # この版の Idle を選ぶ（読み込むたびに Idle.001, .002 と増える）
    cand = [x for x in bpy.data.actions if x.name == "Idle" or x.name.startswith("Idle.")]
    act = cand[i] if i < len(cand) else (cand[-1] if cand else None)
    if arm.animation_data is None: arm.animation_data_create()
    for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
    if act is not None: arm.animation_data.action = act
    sc.frame_set(sc.frame_start)
    bpy.context.view_layer.update()

    # 骨で変形した結果を、そのまま静止メッシュとして取り出す
    dg = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(dg)
    newmesh = bpy.data.meshes.new_from_object(ev)
    newmesh.name = label
    obj = bpy.data.objects.new(label, newmesh)
    sc.collection.objects.link(obj)
    obj.matrix_world = mesh.matrix_world.copy()
    bpy.context.view_layer.update()

    # 読み込んだものは全部消す（骨・内部オブジェクトを残さない）
    for o in list(added):
        bpy.data.objects.remove(o, do_unlink=True)

    made.append((obj, label))
    print("BAKED", label, "->", act.name if act else "アクション無し")

# 背丈を揃えて横（X方向）に並べる
for i, (obj, label) in enumerate(made):
    bpy.context.view_layer.update()
    zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
    h = max(zs) - min(zs)
    s = 1.20 / h
    obj.scale = tuple(v * s for v in obj.scale)
    bpy.context.view_layer.update()
    zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
    xs = [(obj.matrix_world @ v.co).x for v in obj.data.vertices]
    cx = (min(xs) + max(xs)) / 2
    obj.location = (obj.location[0] + (i - (len(made)-1)/2.0)*0.85 - cx,
                    obj.location[1],
                    obj.location[2] - min(zs))
    print("PLACED", label, "x=%.2f" % obj.location[0])

# 真横から見るカメラ
cd = bpy.data.cameras.new("cam"); cd.type='ORTHO'; cd.ortho_scale = 4.6
cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam)
cam.location = (0.0, -14.0, 0.62); cam.rotation_euler = (1.5708, 0, 0)
sc.camera = cam

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED", OUT, "オブジェクト数", len(bpy.data.objects))
