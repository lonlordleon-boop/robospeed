# -*- coding: utf-8 -*-
"""指定した箱の中の頂点の法線（面の向き）を、形から計算し直してなめらかにする。

   生成→貼り直し→骨の写し替えを経たモデルは、脚や靴下の法線が面ごとにバラついていることがある。
   テクスチャは正しいのに、光を当てると白い三角形や灰色の破片のような模様が浮く（影なしで描くと消える）のはこれ。
   位置が同じ頂点（UV の継ぎ目で分かれているもの）をまとめて、まわりの面の向きを面積で重みづけして平均する。
   glTF ファイルの中は Y が上。箱は Blender 座標（Z が上、メートル）で受け取り、中で glTF 座標に直す。
   Blender(x, y, z) = glTF(x, -z, y) なので、glTF = (bx, bz, -by)。

   実行: blender -b --factory-startup -P fixnormals.py -- 入力.glb 出力.glb "x下,x上,y下,y上,z下,z上;..."
"""
import json, struct, sys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
BOXES = [[float(v) for v in b.split(',')] for b in a[2].split(';')]

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

# メッシュを持つノードの世界行列（glTF 座標）
nodes = G['nodes']; parent = {}
for i, nd in enumerate(nodes):
    for c in nd.get('children', []): parent[c] = i
def q2m(q):
    x,y,z,w = q
    return np.array([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),
                     2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]).reshape(3,3)
def wmat(i):
    ch = []; j = i
    while j is not None: ch.append(j); j = parent.get(j)
    Mx = np.eye(4)
    for j in reversed(ch):
        nd = nodes[j]; L = np.eye(4)
        L[:3,:3] = q2m(np.array(nd.get('rotation',[0,0,0,1]),float)) @ np.diag(np.array(nd.get('scale',[1,1,1]),float))
        L[:3,3] = np.array(nd.get('translation',[0,0,0]),float); Mx = Mx @ L
    return Mx
mesh_node = next(i for i, nd in enumerate(nodes) if 'mesh' in nd)
# 骨付きのメッシュは、ノードの行列ではなく骨の行列で動く（glTF の決まり）。
# このモデルでは頂点の位置がそのままメートル単位の Armature 空間なので、
# 一番外側のノード（Armature）の移動だけを足せば世界座標になる。
# ノードの行列（拡大 0.01）を掛けてしまうと、全部が 1cm に縮んで箱の判定が壊れる。
root = mesh_node
while root in parent: root = parent[root]
Mw = np.eye(4); Mw[:3,3] = np.array(nodes[root].get('translation',[0,0,0]), float)

def in_any_box(pw):
    # pw は glTF 世界座標。Blender の箱 (x,y,z) → glTF では (x, z, -y)
    for b in BOXES:
        if b[0] <= pw[0] <= b[1] and b[2] <= -pw[2] <= b[3] and b[4] <= pw[1] <= b[5]:
            return True
    return False

tot = 0; angs = []
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        P = rd(pr['attributes']['POSITION']); N = rd(pr['attributes']['NORMAL'])
        I = rd(pr['indices']).astype(int)[:,0].reshape(-1, 3)
        # 位置が同じ頂点をまとめる鍵
        diag = float(np.linalg.norm(P.max(0) - P.min(0)))
        key = np.round(P / (diag*1e-6)).astype(np.int64)
        kid = {}; vk = np.empty(len(P), np.int64)
        for vi in range(len(P)):
            t = tuple(key[vi]); vk[vi] = kid.setdefault(t, len(kid))
        acc = np.zeros((len(kid), 3))
        for t in I:
            e1 = P[t[1]] - P[t[0]]; e2 = P[t[2]] - P[t[0]]
            fn = np.cross(e1, e2)                       # 長さが面積の2倍＝面積の重み
            for v in t: acc[vk[v]] += fn
        Pw = (Mw[:3,:3] @ P.T).T + Mw[:3,3]
        for vi in range(len(P)):
            if not in_any_box(Pw[vi]): continue
            n = acc[vk[vi]]; l = np.linalg.norm(n)
            if l < 1e-12: continue
            n = n / l
            old = N[vi] / max(1e-9, np.linalg.norm(N[vi]))
            angs.append(np.degrees(np.arccos(np.clip(float(np.dot(old, n)), -1, 1))))
            N[vi] = n; tot += 1
        wr(pr['attributes']['NORMAL'], N)
if angs:
    A_ = np.array(angs)
    print("FN 直した頂点 %d 個。元の法線とのずれ 平均 %.1f度、10度以上 %d 個、最大 %.1f度"
          % (tot, A_.mean(), int((A_ > 10).sum()), A_.max()))
else:
    print("FN 箱の中に頂点が無い")

G['buffers'][0]['byteLength'] = len(bd)
js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = (b'glTF' + struct.pack('<II',2,12+8+len(js)+8+len(bn))
       + struct.pack('<II',len(js),0x4E4F534A) + js + struct.pack('<II',len(bn),0x004E4942) + bn)
open(DST,'wb').write(out); print("FN 書き出し", DST)
