# -*- coding: utf-8 -*-
"""骨の初期姿勢（glTF の各骨ノードの移動・回転・拡大）を、バインド姿勢に戻す。

   glTF の骨ノードに書かれた姿勢は、アニメが無いときの立ち姿になる。
   ビューアはこの姿勢でモデルの囲み箱を測って床に置き、Unity もアニメが無ければこの姿勢で出す。
   animgraft.py でアニメを移したモデルは、移したアニメの1コマの姿勢がここに残り、
   腰が 134° 回った「折れた姿勢」になっていた。プレビューでは身長が小さく測られ、大きく浮いて表示された。

   バインド姿勢は、スキンの逆バインド行列（IBM）から求まる。
   骨の世界行列（メッシュの空間） = IBM の逆行列。
   親が骨なら 骨のローカル = 親の IBM × 自分の IBM の逆行列。親が骨でなければ IBM の逆行列そのもの。
   メッシュのノードと一番上の骨（Hips）が同じ親（Armature）の下にある構造を前提にしている。
   頂点・重み・アニメは触らない（ノードの TRS だけ書き換える）。

   実行: blender -b --factory-startup --python-expr ... ではなく、ふつうの Python でも Blender の Python でも動く。
         blender -b --factory-startup -P bindrest.py -- 入力.glb 出力.glb [確認だけ 1]
"""
import sys, json, struct
import numpy as np

a = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else sys.argv[1:]
SRC, DST = a[0], a[1]
CHECK = len(a) > 2 and a[2] == '1'

b = open(SRC, 'rb').read()
jl = struct.unpack('<I', b[12:16])[0]
J = json.loads(b[20:20+jl])
off = 20 + jl
binlen = struct.unpack('<I', b[off:off+4])[0]
BIN = bytearray(b[off+8:off+8+binlen])

def accessor(i):
    acc = J['accessors'][i]; bv = J['bufferViews'][acc['bufferView']]
    start = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
    n = acc['count']
    return np.frombuffer(bytes(BIN[start:start + n*64]), dtype='<f4').reshape(n, 16)

def mat_from_trs(nd):
    t = nd.get('translation', [0, 0, 0]); r = nd.get('rotation', [0, 0, 0, 1]); s = nd.get('scale', [1, 1, 1])
    x, y, z, w = r
    R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                  [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                  [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    M = np.eye(4); M[:3, :3] = R * np.array(s); M[:3, 3] = t
    return M

def trs_from_mat(M):
    t = M[:3, 3].tolist()
    s = np.linalg.norm(M[:3, :3], axis=0)
    R = M[:3, :3] / s
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        S = 0.5 / np.sqrt(tr + 1.0); w = 0.25 / S
        x = (R[2, 1] - R[1, 2]) * S; y = (R[0, 2] - R[2, 0]) * S; z = (R[1, 0] - R[0, 1]) * S
    else:
        i = int(np.argmax([R[0, 0], R[1, 1], R[2, 2]]))
        if i == 0:
            S = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
            x = 0.25 * S; y = (R[1, 0] + R[0, 1]) / S; z = (R[0, 2] + R[2, 0]) / S; w = (R[2, 1] - R[1, 2]) / S
        elif i == 1:
            S = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
            x = (R[1, 0] + R[0, 1]) / S; y = 0.25 * S; z = (R[2, 1] + R[1, 2]) / S; w = (R[0, 2] - R[2, 0]) / S
        else:
            S = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
            x = (R[0, 2] + R[2, 0]) / S; y = (R[2, 1] + R[1, 2]) / S; z = 0.25 * S; w = (R[1, 0] - R[0, 1]) / S
    q = np.array([x, y, z, w]); q /= np.linalg.norm(q)
    return t, q.tolist(), s.tolist()

skin = J['skins'][0]
joints = skin['joints']
IBM = accessor(skin['inverseBindMatrices'])
# glTF の行列は列優先で並んでいる
IB = {j: IBM[k].reshape(4, 4).T for k, j in enumerate(joints)}
parent = {}
for i, nd in enumerate(J['nodes']):
    for c in nd.get('children', []): parent[c] = i

worst = 0.0
for j in joints:
    p = parent.get(j)
    if p in IB: L = IB[p] @ np.linalg.inv(IB[j])
    else:       L = np.linalg.inv(IB[j])
    nd = J['nodes'][j]
    cur = mat_from_trs(nd)
    diff = np.abs(cur - L).max()
    worst = max(worst, diff)
    if CHECK:
        print("BR %-14s 今の姿勢とバインド姿勢の差 %.4f" % (nd.get('name'), diff))
    t, q, s = trs_from_mat(L)
    nd['translation'] = t; nd['rotation'] = q; nd['scale'] = s
print("BR 骨 %d 本  いちばん大きい差 %.4f" % (len(joints), worst))
if CHECK: sys.exit(0)

js = json.dumps(J, separators=(',', ':')).encode('utf-8')
js += b' ' * ((4 - len(js) % 4) % 4)
out = bytearray()
total = 12 + 8 + len(js) + 8 + len(BIN)
out += struct.pack('<III', 0x46546C67, 2, total)
out += struct.pack('<II', len(js), 0x4E4F534A) + js
out += struct.pack('<II', len(BIN), 0x004E4942) + BIN
open(DST, 'wb').write(out)
print("BR 書き出し", DST, len(out))
