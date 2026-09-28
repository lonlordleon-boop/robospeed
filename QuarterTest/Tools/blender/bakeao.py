# -*- coding: utf-8 -*-
"""まわりの形でさえぎられる度合い（アンビエントオクルージョン）を計算して、テクスチャに焼き込む。

   生成そのままのテクスチャは、色はあるが陰が無い。
   襟の内側、袖の付け根、シャツと短パンの境目、髪の束の間、顎の下。
   そういう「奥まっていて光が入りにくい所」が、絵の上では明るいままなので平たく見える。
   girl_v55 は貼り直しでそれが描き込まれているため、光を当てなくても立体に見える。

   ここでは Cycles に光のさえぎられ方を計算させ、元の色に掛け算する。
   計算は場面ぜんぶを見るので、髪が額に落とす影や、服が素体に落とす影も入る。

   強さ1.0で真っ黒まで落ちるので、下限を決めて締める。
   仕上がりの色 = 元の色 × max(下限, 1 - 強さ×(1 - 遮蔽))

   テクスチャはメッシュごとに別なので、メッシュごとに焼いて、そのメッシュの絵に掛ける。
   画像は Blender の中で直接書き換えてから書き出すので、swaptex.py は要らない。

   実行: blender -b --factory-startup -P bakeao.py -- 入力.glb 出力.glb
         [強さ 既定0.55] [下限 既定0.40] [届く距離 m 既定0.12] [サンプル数 既定32] [メッシュ名,... 既定すべて]
"""
import bpy, sys, os
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
STR  = float(a[2]) if len(a) > 2 else 0.55
FLOOR= float(a[3]) if len(a) > 3 else 0.40
DIST = float(a[4]) if len(a) > 4 else 0.12
SAMP = int(a[5]) if len(a) > 5 else 32
ONLY = a[6].split(',') if len(a) > 6 and a[6] else None

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm and arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()

sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = SAMP
sc.cycles.bake_type = 'AO'
sc.render.bake.margin = 8
# 焼く前に真っ白で埋めておき、消さずに焼く。
# 真っ黒に消してから焼くと、UVの島の外（テクスチャの空き地）が0のままになり、
# そこに掛け算して縁が暗くなる。texpad.py で塗り広げた縁が黒ずむ。
sc.render.bake.use_clear = False
if sc.world is None: sc.world = bpy.data.worlds.new("w")
sc.world.light_settings.distance = DIST     # この距離より遠い物は影を落とさない

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if ONLY: meshes = [o for o in meshes if o.name in ONLY]
print("BA 対象 %s（強さ %.2f、下限 %.2f、届く距離 %.2f m、サンプル %d）"
      % ([o.name for o in meshes], STR, FLOOR, DIST, SAMP))

for me in meshes:
    mats = [m for m in me.data.materials if m and m.use_nodes]
    if not mats:
        print("BA %s: 材質が無いので飛ばす" % me.name); continue
    base = None
    for m in mats:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image: base = n.image; break
        if base: break
    if base is None:
        print("BA %s: 絵が無いので飛ばす" % me.name); continue
    W, H = base.size
    ao = bpy.data.images.new("ao_" + me.name, W, H, alpha=False, float_buffer=False)
    ao.pixels = [1.0] * (W * H * 4)          # 白で埋めてから焼く（島の外は白のまま＝暗くしない）

    # 焼き先になる画像ノードを、その材質の「いま選ばれているノード」にする
    tmp = []
    for m in mats:
        nd = m.node_tree.nodes.new('ShaderNodeTexImage')
        nd.image = ao
        m.node_tree.nodes.active = nd
        nd.select = True
        tmp.append((m, nd))

    for o in bpy.data.objects: o.select_set(False)
    me.select_set(True); bpy.context.view_layer.objects.active = me
    print("BA %s: %dx%d を焼く…" % (me.name, W, H))
    bpy.ops.object.bake(type='AO')

    A = np.array(base.pixels[:], dtype=np.float32).reshape(H, W, 4)
    O = np.array(ao.pixels[:], dtype=np.float32).reshape(H, W, 4)[:, :, 0]
    mul = np.clip(1.0 - STR * (1.0 - O), FLOOR, 1.0)
    A[:, :, :3] *= mul[:, :, None]
    base.pixels = A.ravel().tolist()
    base.pack()
    print("BA %s: 掛け算した（遮蔽の平均 %.3f、掛けた値の最小 %.3f）" % (me.name, float(O.mean()), float(mul.min())))

    for m, nd in tmp: m.node_tree.nodes.remove(nd)
    bpy.data.images.remove(ao)

bpy.ops.object.select_all(action='SELECT')
# 絵は JPEG で書き出す。PNG のままだとファイルが 13MB から 23MB に膨らんだ
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_image_format='JPEG', export_jpeg_quality=92,
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True)
print("BA 書き出し", DST, os.path.getsize(DST))
