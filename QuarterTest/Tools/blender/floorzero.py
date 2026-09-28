# -*- coding: utf-8 -*-
"""素の姿勢（アニメを外した立ち姿）の足が、ちょうど床（高さ0）に着くようにモデル全体を上下させる。

   生成したばかりのモデルは、骨の付け方の都合で立ち姿が数センチ浮いていることがある。
   その状態で liftdip.py を掛けると「床＝浮いた足元」と見なしてしまい、浮きが直らない。
   だから先にこの道具で立ち姿を床に着け、そのあとで liftdip.py を掛けること。

   直すのは一番外側の入れ物（Armature）の位置だけで、骨も重みもアニメも触らない。
   glTF ファイルの中は Y が上。Blender で測った高さ（Z）は、そのまま glTF の Y に対応する。

   実行: blender -b --factory-startup -P floorzero.py -- 入力.glb 出力.glb
"""
import bpy, sys, json, struct

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere'))
if arm.animation_data is None: arm.animation_data_create()
arm.animation_data.action = None            # 素の姿勢にする
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get(); ev = mesh.evaluated_get(dg); me = ev.to_mesh()
z = min((ev.matrix_world @ v.co).z for v in me.vertices); ev.to_mesh_clear()
print("FZ 立ち姿の最下点 %.4f m（%.1f cm）" % (z, z*100))

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
bd = bytearray(raw[Jm[0x004E4942][0]:Jm[0x004E4942][0]+Jm[0x004E4942][1]])

for i in G['scenes'][G.get('scene', 0)]['nodes']:
    nd = G['nodes'][i]
    t = list(nd.get('translation', [0.0, 0.0, 0.0]))
    t[1] -= z
    nd['translation'] = [float(x) for x in t]
    print("FZ %s の位置を %s にした" % (nd.get('name'), nd['translation']))

G['buffers'][0]['byteLength'] = len(bd)
js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' '*((4-len(js) % 4) % 4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn) % 4) % 4)
out = (b'glTF' + struct.pack('<II', 2, 12+8+len(js)+8+len(bn))
       + struct.pack('<II', len(js), 0x4E4F534A) + js
       + struct.pack('<II', len(bn), 0x004E4942) + bn)
open(DST, 'wb').write(out); print("FZ 書き出し", DST)
