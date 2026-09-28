# -*- coding: utf-8 -*-
"""腕の重みを、骨の位置から付け直す。

   自動リグは、二の腕の袖まで「前腕」の骨に付けてしまうことがある（お嬢様（小学生）は
   二の腕の頂点の重みが 前腕 20%・肩 15%・上腕 4.5% だった）。すると肘を曲げたとき
   二の腕ごと折れ曲がって見える。この道具は、肩→上腕→前腕→手の骨の並びに頂点を
   投影し、どの骨の区間にあるかで重みを付け直す。関節のまわり（±幅）は隣の骨と混ぜる。

   対象は、腕の骨の並びから半径以内にある、髪でない頂点。
   髪かどうかは重みではなくテクスチャの色で決める（暗い＝髪）。
   袖の頂点にも頭の重みが混ざっていることがあり、重みで分けると袖の一部が頭に
   ついて行って肩が裂けるため。glTF ファイルの中は Y が上、位置はメートル。
   骨付きメッシュの頂点は一番外側のノードの移動だけ足せば世界座標になる。

   実行: blender -b --factory-startup -P armweights.py -- 入力.glb 出力.glb [半径 既定0.07] [混ぜ幅 既定0.02] [胴の幅 既定0.15]
"""
import json, struct, sys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
RAD = float(a[2]) if len(a) > 2 else 0.07
BLEND = float(a[3]) if len(a) > 3 else 0.02
BODYX = float(a[4]) if len(a) > 4 else 0.15      # これより体の軸に近い頂点は胴とみなす

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
nodes = G['nodes']; parent = {}
for i, nd in enumerate(nodes):
    for c in nd.get('children', []): parent[c] = i
n2i = {nd.get('name',''): i for i, nd in enumerate(nodes)}
def q2m(q):
    x,y,z,w = q
    return np.array([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),
                     2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]).reshape(3,3)
def wpos(i):
    ch = []; j = i
    while j is not None: ch.append(j); j = parent.get(j)
    Mx = np.eye(4)
    for j in reversed(ch):
        nd = nodes[j]; L = np.eye(4)
        L[:3,:3] = q2m(np.array(nd.get('rotation',[0,0,0,1]),float)) @ np.diag(np.array(nd.get('scale',[1,1,1]),float))
        L[:3,3] = np.array(nd.get('translation',[0,0,0]),float); Mx = Mx @ L
    return Mx[:3,3]
joints = G['skins'][0]['joints']; jn = [nodes[j].get('name') for j in joints]
HEADS = {i for i, n in enumerate(jn) if 'head' in n.lower()}
# テクスチャを読んで、頂点ごとの明るさを引けるようにする（暗ければ髪）
import bpy, os, tempfile
img0 = G['images'][0]; bv = G['bufferViews'][img0['bufferView']]
png = bytes(bd[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']])
tmp = os.path.join(tempfile.gettempdir(), "_aw_tex.png"); open(tmp,'wb').write(png)
im = bpy.data.images.load(tmp); IW, IH = im.size
PIX = np.array(im.pixels[:], dtype=np.float32).reshape(IH, IW, 4)
def tex_lum(uv):
    # glTF の v は上が 0、Blender の画素は下の行が先頭なので上下を返す
    px = min(IW-1, max(0, int(uv[0]*IW))); py = min(IH-1, max(0, int((1.0-uv[1])*IH)))
    c = PIX[py, px]; return 0.299*c[0] + 0.587*c[1] + 0.114*c[2]
mesh_node = next(i for i, nd in enumerate(nodes) if 'mesh' in nd)
root = mesh_node
while root in parent: root = parent[root]
T = np.array(nodes[root].get('translation',[0,0,0]), float)

def seg_param(p, A, B):
    d = B - A; l2 = float(d @ d)
    t = 0.0 if l2 < 1e-12 else float(np.clip(((p - A) @ d) / l2, 0.0, 1.0))
    q = A + d*t; return t, float(np.linalg.norm(p - q))

tot = 0
for side in ('Left', 'Right'):
    names = [side+'Shoulder', side+'Arm', side+'ForeArm', side+'Hand']
    ji = [jn.index(n) for n in names]; ARMSET = set(ji)
    P = [wpos(n2i[n]) for n in names]
    # 手の先は、前腕→手の向きに手の長さぶん伸ばす
    hand_len = np.linalg.norm(P[3] - P[2]) * 0.9
    P.append(P[3] + (P[3] - P[2]) / max(1e-9, np.linalg.norm(P[3] - P[2])) * hand_len)
    # 区間ごとの持ち主：肩→上腕の付け根は肩、上腕付け根→肘は上腕、肘→手首は前腕、手首→先は手
    owner = [0, 1, 2, 3]
    L = [float(np.linalg.norm(P[k+1] - P[k])) for k in range(4)]
    cum = np.concatenate([[0.0], np.cumsum(L)])
    for mesh in G['meshes']:
        for pr in mesh['primitives']:
            V = rd(pr['attributes']['POSITION']) + T
            J = rd(pr['attributes']['JOINTS_0']).astype(int); W = rd(pr['attributes']['WEIGHTS_0'])
            UV = rd(pr['attributes']['TEXCOORD_0'])
            for vi in range(len(V)):
                p = V[vi]
                if tex_lum(UV[vi]) < 0.25: continue        # 髪（黒い）
                # もともと腕の骨（か、袖に混ざった頭）の重みを持つ頂点だけ。
                # 手のそばにあるスカートや腰まで腕に付けると、そこが引き裂かれる。
                # 胴やスカートの頂点（体の軸に近く、肩より下）は、腕と融合していても触らない
                if abs(p[0]) < BODYX and p[1] < P[1][1] - 0.08: continue
                # 肩の関節より 4cm 以上高い所は襟や首。腕ではないので触らない
                if p[1] > P[1][1] + 0.04: continue
                armw = sum(W[vi,k] for k in range(4) if J[vi,k] in ARMSET)
                headw = sum(W[vi,k] for k in range(4) if J[vi,k] in HEADS)
                if armw < 0.15 and headw < 0.5: continue
                best = None
                for k in range(4):
                    t, d = seg_param(p, P[k], P[k+1])
                    if best is None or d < best[1]: best = (cum[k] + t*L[k], d, k)
                s, d, k = best
                if d > RAD: continue
                if k == 0 and s < L[0]*0.35: continue      # 肩の付け根より内側は胴なので触らない
                # 骨の並びに沿った位置 s から、隣り合う骨を混ぜる
                w = np.zeros(4)
                w[owner[k]] = 1.0
                for kk in range(1, 4):                     # 関節 kk（上腕付け根・肘・手首）
                    dj = s - cum[kk]
                    if abs(dj) < BLEND:
                        f = (dj + BLEND) / (2*BLEND)       # 手前で 0 → 通り過ぎて 1
                        w[:] = 0.0; w[owner[kk-1]] = 1.0 - f; w[owner[kk]] = f
                # 手首から先は、腰やスカートと融合していることがあるので元の重みへ戻していく。
                # 肘までは付け直した重みそのまま、肘から前腕の6割の所で元の重みに戻す。
                f = 1.0 if s <= cum[2] else max(0.0, 1.0 - (s - cum[2]) / (0.6*L[2]))
                if f <= 0.0: continue
                mix = {}
                for c in range(4):
                    if W[vi,c] > 0: mix[int(J[vi,c])] = mix.get(int(J[vi,c]), 0.0) + W[vi,c]*(1.0 - f)
                for c in range(4):
                    if w[c] > 0: mix[ji[c]] = mix.get(ji[c], 0.0) + w[c]*f
                top = sorted(mix.items(), key=lambda x: -x[1])[:4]
                ssum = sum(v for _, v in top)
                for c in range(4):
                    if c < len(top): J[vi,c] = top[c][0]; W[vi,c] = top[c][1]/ssum
                    else: J[vi,c] = 0; W[vi,c] = 0.0
                tot += 1
            wr(pr['attributes']['JOINTS_0'], J); wr(pr['attributes']['WEIGHTS_0'], W)
    print("AW %s の腕: 骨の並び 肩(%.2f,%.2f,%.2f) 肘(%.2f,%.2f,%.2f) 手首(%.2f,%.2f,%.2f)"
          % (side, *P[1], *P[2], *P[3]))
print("AW 重みを付け直した頂点 %d 個" % tot)
G['buffers'][0]['byteLength'] = len(bd)
js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = (b'glTF' + struct.pack('<II',2,12+8+len(js)+8+len(bn)) + struct.pack('<II',len(js),0x4E4F534A) + js
       + struct.pack('<II',len(bn),0x004E4942) + bn)
open(DST,'wb').write(out); print("AW 書き出し", DST)
