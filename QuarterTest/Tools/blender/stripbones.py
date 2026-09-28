# -*- coding: utf-8 -*-
"""部品から、指定した骨の重みを外す。外したぶんは残りの骨に配り直す。

   袖なしのシャツを素体から重みを写すと、袖ぐりの近くの頂点が上腕の骨の重みをもらう。
   素体の上腕がすぐそばにあるからだが、袖なしの服は腕に付いていってはいけない。
   走りで腕を振るたびに胴の布が腕へ引っぱられ、縞が斜めに裂けて見えた。

   やることは headclean.py と同じ。指定した骨の重みを0にして、残りの重みで割り直す。
   残りが無くなった頂点は、x の符号で左右を見て「受け皿の骨」（既定 LeftShoulder / RightShoulder）に付ける。
   glTF ファイルを直接読み書きするので、絵も形も一切変わらない。

   実行: blender -b --factory-startup -P stripbones.py --
         入力.glb 出力.glb 種類 外す骨,... [受け皿の骨 左,右 既定 LeftShoulder,RightShoulder]
   例:   ... -- doll.glb out.glb cloth LeftArm,RightArm,LeftForeArm,RightForeArm,LeftHand,RightHand
"""
import json, struct, sys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, KIND = a[0], a[1], a[2]
STRIP = set(a[3].split(','))
FALL = a[4].split(',') if len(a) > 4 and a[4] else ['LeftShoulder', 'RightShoulder']

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO+BL])
COMP = {5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def lay(i):
    ac = G['accessors'][i]; n = NUM[ac['type']]; f, s = COMP[ac['componentType']]
    bv = G['bufferViews'][ac['bufferView']]
    return ac, n, f, bv.get('byteOffset',0)+ac.get('byteOffset',0), bv.get('byteStride') or n*s
def rd(i):
    ac, n, f, b, st = lay(i); o = np.zeros((ac['count'], n))
    for k in range(ac['count']): o[k] = struct.unpack_from('<'+f*n, bd, b+k*st)
    return o
def wr(i, arr):
    ac, n, f, b, st = lay(i)
    for k in range(ac['count']): struct.pack_into('<'+f*n, bd, b+k*st, *arr[k])

nodes = G['nodes']
joints = G['skins'][0]['joints']; jn = [nodes[j].get('name') for j in joints]
SIDX = {i for i, n in enumerate(jn) if n in STRIP}
FIDX = [jn.index(FALL[0]), jn.index(FALL[1])]
print("SB 外す骨 %s → 番号 %s   受け皿 %s" % (sorted(STRIP), sorted(SIDX), FALL))

tot = 0; fell = 0; moved = {}
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        mat = G['materials'][pr['material']].get('name', '') if 'material' in pr else ''
        kind = mat.split(':')[0] if ':' in mat else 'body'
        if kind != KIND:
            continue
        print("SB %-18s（種類 %s）を直す" % (mat[:18], kind))
        P = rd(pr['attributes']['POSITION'])
        J = rd(pr['attributes']['JOINTS_0']).astype(int)
        W = rd(pr['attributes']['WEIGHTS_0'])
        for vi in range(len(P)):
            hit = False
            for k in range(4):
                if J[vi,k] in SIDX and W[vi,k] > 0:
                    moved[jn[J[vi,k]]] = moved.get(jn[J[vi,k]], 0) + 1
                    W[vi,k] = 0.0; hit = True
            if not hit: continue
            tot += 1
            s = W[vi].sum()
            if s <= 1e-6:
                W[vi] = 0.0; J[vi,0] = FIDX[0] if P[vi,0] > 0 else FIDX[1]; W[vi,0] = 1.0
                fell += 1
            else:
                W[vi] /= s
        wr(pr['attributes']['WEIGHTS_0'], W); wr(pr['attributes']['JOINTS_0'], J)
print("SB 直した頂点 %d 個（受け皿へ付け直した %d 個）  外した重みの元: %s"
      % (tot, fell, sorted(moved.items(), key=lambda x: -x[1])))

G['buffers'][0]['byteLength'] = len(bd)
js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = (b'glTF' + struct.pack('<II',2,12+8+len(js)+8+len(bn))
       + struct.pack('<II',len(js),0x4E4F534A) + js
       + struct.pack('<II',len(bn),0x004E4942) + bn)
open(DST,'wb').write(out); print("SB 書き出し", DST)
