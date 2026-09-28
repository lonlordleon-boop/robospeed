# -*- coding: utf-8 -*-
"""骨の無い置物（シーソーの男の子）の腕を、肩を支点に回して、握りこぶしを取っ手へ下ろす（2026年9月23日）。

   三面図では握りこぶしが胸の高さにあったので、立体でも取っ手（腿の高さ）より上に浮いて見えた。
   作り直すとまた30クレジットかかるので、形だけを動かす。
   左右それぞれ、
   ・肩の点 S と、今の握りこぶしの中心 F を決める（F は胸より前に出ている所の中心）
   ・F が目標の T へ来るよう、S を通る左右の軸（x 軸）まわりに回し、腕の長さも S からの距離の比で縮める
   ・動かす量は、肩からの距離でなめらかに 0 → 1（肩の付け根は動かさず、ひじから先がいっぱいに動く）
   動かすのは腕だけ（胸より前に出た所と、胴より外の袖・上腕。どちらもなめらかな重みで、境目で急に切らない）。胴・脚・顔は触らない。

   座標は boyfit.py の後（Blender：x 左右・y 前が −・z 上、原点はお尻）。
   実行: blender -b -P armdown.py -- 入力.glb 出力.glb 目標の高さ,前（例 0.263,-0.28） 目標の左右（例 0.10） [確認画像.png]"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(a[0]), os.path.abspath(a[1])
TZ, TY = [float(v) for v in a[2].split(',')]
TX = float(a[3])
SHOT = os.path.abspath(a[4]) if len(a) > 4 else None
def log(s): print("[armdown] " + str(s))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
me = next(o for o in bpy.context.scene.objects if o.type == 'MESH'); m = me.data
P = np.array([tuple(v.co) for v in m.vertices])
Q = P.copy()
for s in (-1, 1):
    side = P[:, 0] * s > 0.02
    fore = side & (P[:, 2] > 0.30) & (P[:, 2] < 0.62) & (P[:, 1] < -0.24)      # 胸より前に出た前腕と握りこぶし
    F = P[fore & (P[:, 1] < np.percentile(P[fore, 1], 25))].mean(0)            # 一番前の4分の1の中心 = 握りこぶし
    upper = side & (np.abs(P[:, 0]) > 0.17) & (P[:, 2] > 0.36) & (P[:, 2] < 0.70) & (P[:, 1] < 0.06)
    top = P[upper & (P[:, 2] > 0.58)]
    S = np.array([top[:, 0].mean(), top[:, 1].mean(), top[:, 2].mean()]) if len(top) else np.array([s * 0.22, -0.02, 0.62])
    T = np.array([s * TX, TY, TZ])
    v0, v1 = (F - S)[1:], (T - S)[1:]                                           # y-z の面で回す
    ang = math.atan2(v1[1], v1[0]) - math.atan2(v0[1], v0[0])
    k = np.linalg.norm(v1) / np.linalg.norm(v0)
    L = np.linalg.norm(F - S)
    # 動かす重み = 肩からの距離の重み × 腕らしさ。腕らしさは「胸より前に出ている」か「胴より外にある」をなめらかに取る。
    # 頂点を選んで動かすと、袖の後ろ側が取り残されて、袖と腕の境目が裂けた
    mf = np.clip((-P[:, 1] - 0.19) / 0.06, 0, 1)                                # 胸（前 0.17）より前
    ms = np.clip((np.abs(P[:, 0]) - 0.19) / 0.05, 0, 1)                         # 胴より外（袖・上腕）
    mz = np.clip((P[:, 2] - 0.28) / 0.06, 0, 1) * np.clip((0.74 - P[:, 2]) / 0.06, 0, 1)   # 腿より上・首より下
    mk = np.maximum(mf, ms) * mz * (P[:, 0] * s > -0.02)
    arm = mk > 0
    d = P[arm] - S
    t = np.clip((np.linalg.norm(d, axis=1) / L - 0.15) / 0.45, 0, 1); w = t * t * (3 - 2 * t) * mk[arm]
    c, sn = np.cos(ang * w), np.sin(ang * w)
    y, z = d[:, 1], d[:, 2]
    y2, z2 = y * c - z * sn, y * sn + z * c
    sc = 1 + (k - 1) * w
    x2 = d[:, 0] + (T[0] - F[0]) * w                                             # 左右は、握りこぶしを取っ手の幅へ寄せる
    Q[arm] = S + np.c_[x2, y2 * sc, z2 * sc]
    log("side %+d: 肩 %s 握りこぶし %s → 目標 %s / 回す角度 %.1f度 / 長さ %.2f倍 / 動かした頂点 %d"
        % (s, np.round(S, 3), np.round(F, 3), np.round(T, 3), math.degrees(ang), k, arm.sum()))
for i, v in enumerate(m.vertices): v.co = Vector(tuple(float(c) for c in Q[i]))
m.update()
if SHOT:
    # 取っ手の代わりの棒（左右 ±0.14・高さ TZ・前 TY）と一緒に、横と前から
    bpy.ops.mesh.primitive_cylinder_add(radius=0.028, depth=0.28, location=(0, TY, TZ), rotation=(0, math.pi / 2, 0))
    sc = bpy.context.scene
    cd = bpy.data.cameras.new('c'); cd.type = 'ORTHO'; cd.ortho_scale = 2.2
    cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
    sc.view_settings.view_transform = 'Standard'
    w_ = bpy.data.worlds.new('w'); sc.world = w_; w_.color = (1, 1, 1)
    sc.render.resolution_x = 360; sc.render.resolution_y = 420
    files = []
    for k_, az in enumerate((0, 90, 35)):
        dv = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), 0.12)).normalized()
        cam.location = Vector((0, 0, 0.45)) + dv * 8; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
        fn = os.path.join(os.path.dirname(SHOT), '_ad_%d.png' % k_); files.append(fn)
        sc.render.filepath = fn; bpy.ops.render.render(write_still=True)
    imgs = [bpy.data.images.load(f) for f in files]; W, H = imgs[0].size
    buf = np.ones((H, W * 3, 4), np.float32)
    for k_, im in enumerate(imgs):
        px = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(px); buf[:, k_ * W:(k_ + 1) * W] = px.reshape(H, W, 4)
    o = bpy.data.images.new('o', W * 3, H); o.pixels.foreach_set(buf.ravel()); o.filepath_raw = SHOT; o.file_format = 'PNG'; o.save()
    bpy.data.objects.remove(bpy.data.objects['Cylinder'], do_unlink=True)
bpy.ops.object.select_all(action='DESELECT'); me.select_set(True); bpy.context.view_layer.objects.active = me
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_yup=True,
                          export_animations=False, export_skins=False, export_image_format='JPEG', export_jpeg_quality=90)
log("書き出し: " + OUT)
