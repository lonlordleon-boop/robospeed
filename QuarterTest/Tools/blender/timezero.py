# -*- coding: utf-8 -*-
"""glb のアニメの時間を、クリップごとに 0 秒始まりへ戻す。

   Blender の glTF 書き出し（NLA のクリップごと）を通すと、クリップが 1 コマ（1/24 秒）後ろへずれて
   0.0417 秒から始まった（元の girl_v55.glb は 0 秒始まり）。繰り返し再生すると継ぎ目で 1 コマ止まる。
   各クリップの時間の入力（アクセサ）から、そのクリップのいちばん早い時刻を引く。姿勢の値は触らない。
   同じアクセサを複数のクリップが共有していても 1 回だけ引く。

   実行: python または blender の python で timezero.py 入力.glb 出力.glb [並べる順 Idle,Run,...]
         （blender -b --factory-startup --python-expr から呼んでもよい）
"""
import sys, json, struct
import numpy as np

args = [x for x in sys.argv[1:] if x.endswith('.glb')]
SRC, DST = args[0], args[1]
# 3番目にクリップ名を , でつないで書くと、その順にクリップを並べ直す。
# Blender の書き出しは並び順も変えた（Wave が先頭になった）。preview.html はクリップを番号でそろえるので、元の順に戻す
rest = [x for x in sys.argv[1:] if not x.endswith('.glb') and ',' in x]
ORDER = rest[0].split(',') if rest else None
raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0] + Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO + BL])

done = set()
for an in G.get('animations', []):
    ins = sorted({s['input'] for s in an['samplers']})
    t0 = min(G['accessors'][i]['min'][0] for i in ins)
    for i in ins:
        if i in done: continue
        ac = G['accessors'][i]; bv = G['bufferViews'][ac['bufferView']]
        b = bv.get('byteOffset', 0) + ac.get('byteOffset', 0); n = ac['count']
        v = np.frombuffer(bytes(bd[b:b + 4 * n]), dtype='<f4') - np.float32(t0)
        v = np.maximum(v, 0)
        # 1/24 秒の刻みにそろえる。引き算の端数（1.0 が 0.99999994 になる）が残ると、FBX にしたとき最後のコマが
        # 切り捨てられ、手を振る動きが 25 コマから 24 コマに縮んだ
        g = np.round(v * 24.0) / 24.0
        v = np.where(np.abs(v - g) < 1e-3, g, v).astype('<f4')
        bd[b:b + 4 * n] = v.tobytes()
        ac['min'] = [float(v.min())]; ac['max'] = [float(v.max())]
        done.add(i)
    print("TZ %s: %.4f 秒ずらして 0 秒始まりにした" % (an.get('name'), t0))
if ORDER:
    rank = {n: i for i, n in enumerate(ORDER)}
    G['animations'].sort(key=lambda an: rank.get(an.get('name'), len(ORDER)))
    print("TZ 並び順", [an.get('name') for an in G['animations']])

js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
bn = bytes(bd); bn += b'\x00' * ((4 - len(bn) % 4) % 4)
out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
open(DST, 'wb').write(out)
print("TZ 書き出し", DST, len(out))
