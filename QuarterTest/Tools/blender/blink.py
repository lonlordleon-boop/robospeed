# -*- coding: utf-8 -*-
"""まばたきの形（シェイプキー）を足す。
   このモデルの目は絵で描かれているので、上まぶたにあたる範囲を下まぶたの高さまで下ろすと、
   描かれた目がそのまま細くなり、閉じたように見える。
   下げる量は高さだけで決め（横方向の重みは高さに依らない）、面が折り返らないようにする。
   まぶたより上（額）は、下げた量をなめらかに 0 へ戻す。
   実行: blender -b --factory-startup -P blink.py -- 入力.glb 出力.glb 目の中心x,y 横半径,奥半径 下まぶたz,上まぶたz,戻し終わりz 強さ [名前]"""
import bpy, sys
from mathutils import Vector

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
CX, CY = [float(x) for x in a[2].split(',')]
RX, RY = [float(x) for x in a[3].split(',')]
ZLO, ZHI, ZFADE = [float(x) for x in a[4].split(',')]
AMT = float(a[5]) if len(a) > 5 else 0.9
NAME = a[6] if len(a) > 6 else "Blink"

def smooth(t):
    t = max(0.0, min(1.0, t))
    return t*t*(3-2*t)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"):
        bpy.data.objects.remove(o, do_unlink=True)
me = next(o for o in bpy.data.objects if o.type == 'MESH')
mesh = me.data
if mesh.shape_keys is None:
    me.shape_key_add(name="Basis", from_mix=False)
kb = me.shape_key_add(name=NAME, from_mix=False)

# メッシュは骨の下にぶら下がっているので、判定は世界の座標で行い、書き戻すときに戻す
MW = me.matrix_world; MWI = MW.inverted()
moved = 0; maxd = 0.0
for i, v in enumerate(mesh.vertices):
    p = MW @ v.co
    # 横方向の重み（左右の目のどちらか近いほう）
    wx = max(smooth(1.0 - abs(p.x - CX)/RX), smooth(1.0 - abs(p.x + CX)/RX))
    if wx <= 0.0: continue
    wy = smooth(1.0 - abs(p.y - CY)/RY)
    if wy <= 0.0: continue
    w = wx * wy
    # 高さの形。まぶたの間は高さに比例して下げ、額へ向かってなめらかに戻す
    if p.z <= ZLO: continue
    if p.z <= ZHI: f = p.z - ZLO
    else:          f = (ZHI - ZLO) * (1.0 - smooth((p.z - ZHI)/(ZFADE - ZHI)))
    d = AMT * w * f
    if d <= 1e-6: continue
    kb.data[i].co = MWI @ Vector((p.x, p.y, p.z - d))
    moved += 1; maxd = max(maxd, d)
print("BL 動かした頂点 %d 個、最大の下げ %.4f" % (moved, maxd))

kb.value = 0.0
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_animation_mode='NLA_TRACKS',
                          export_skins=True, export_morph=True, export_yup=True)
print("BL 書き出し", DST)
