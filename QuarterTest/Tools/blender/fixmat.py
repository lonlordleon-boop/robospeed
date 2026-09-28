# -*- coding: utf-8 -*-
"""生成された材質に付いてくる余計な設定を落とす。

   Meshy の出力には、前の素体には無かった設定が三つ乗っていた（新しい素体 es4）。

     金属度 1.0          肌が磨いた金属として計算され、光を全反射して飛ぶ
     発光テクスチャ      肌の絵が「自分で光る」設定としても貼られ、色が二重になって黄色く濁る
     鏡面の色 2.0 倍     さらに白飛びを足す

   金属度だけ直しても黄色は消えなかった。発光が本体だった。
   前の素体・服・髪・靴は、どれも baseColorTexture だけの素直な材質で、
   金属度0・粗さ0.8・発光なし・鏡面は既定の0.5。それに合わせる。

   絵には手を触れない。材質の数値だけを書き換える。

   実行: blender -b --factory-startup -P fixmat.py --
         入力.glb 出力.glb [金属度 既定0.0] [粗さ 既定0.8] [メッシュ名,... 既定すべて]
"""
import bpy, sys, os

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
MET = float(a[2]) if len(a) > 2 else 0.0
ROU = float(a[3]) if len(a) > 3 else 0.8
ONLY = a[4].split(',') if len(a) > 4 and a[4] else None

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)

n = 0
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    if ONLY is not None and o.name not in ONLY: continue
    for m in o.data.materials:
        if not m or not m.use_nodes: continue
        b = next((x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED'), None)
        if not b: continue
        old = (b.inputs["Metallic"].default_value, b.inputs["Roughness"].default_value)
        b.inputs["Metallic"].default_value = MET
        b.inputs["Roughness"].default_value = ROU
        msg = "金属 %.3f→%.3f  粗さ %.3f→%.3f" % (old[0], MET, old[1], ROU)

        # 発光を落とす。つないである絵も外す（外さないと書き出しで emissiveTexture が復活する）
        for key in ("Emission Color", "Emission"):
            s = b.inputs.get(key)
            if s is None: continue
            if s.is_linked:
                for lk in list(s.links): m.node_tree.links.remove(lk)
                msg += "  発光の絵を外した"
            try: s.default_value = (0.0, 0.0, 0.0, 1.0)
            except Exception: pass
        s = b.inputs.get("Emission Strength")
        if s is not None and s.default_value != 0.0:
            msg += "  発光 %.2f→0" % s.default_value
            s.default_value = 0.0

        # 鏡面を既定へ戻す
        for key in ("Specular IOR Level", "Specular"):
            s = b.inputs.get(key)
            if s is None: continue
            if abs(s.default_value - 0.5) > 1e-6:
                msg += "  鏡面 %.2f→0.50" % s.default_value
                s.default_value = 0.5
        s = b.inputs.get("Specular Tint")
        if s is not None:
            try: s.default_value = (1.0, 1.0, 1.0, 1.0)
            except Exception: pass

        # つながっていない発光ノードが残っていると書き出しに乗ることがあるので掃除する
        for nd in list(m.node_tree.nodes):
            if nd.type == 'EMISSION':
                m.node_tree.nodes.remove(nd); msg += "  発光ノードを削除"

        print("FM %-20s %-18s %s" % (o.name[:20], m.name[:18], msg))
        n += 1
print("FM 直した材質 %d" % n)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True, export_image_format='JPEG', export_jpeg_quality=92)
print("FM 書き出し", DST, os.path.getsize(DST))
