# -*- coding: utf-8 -*-
"""【使っていない】girl_v46 で試したところ、どのクリップも悪化したので不採用。
   腕の重みが小さい頂点は、胴と腕のつなぎ目をなめらかにする役目を持っている。
   それを切ると境目が硬くなり、伸びた辺は Idle 26→43、歩き 58→139、スキップ 266→327 と増えた。
   同じことをやりたくなったら、まずこの数字を思い出すこと。

   脇より下に乗っている腕の重みを外す。
   自動リグは胴の下のほうにも腕の重みを少し配ることがある。
   腕を下ろしている間は目立たないが、手を上げるとその頂点が引っぱられ、
   腰のあたりの面が引き伸ばされて折れ目になる。
   脇の高さより下では腕の重みを 0 にし、なめらかに戻す。外した分は胴の骨へ渡す。
   実行: blender -b --factory-startup --python armclean.py -- 入力.glb 出力.glb [脇の高さ] [なじませる幅] [腕とみなす重み]"""
import json, struct, sys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
ARMPIT = float(a[2]) if len(a) > 2 else None
FADE = float(a[3]) if len(a) > 3 else 0.06
# 腕の重みの合計がこれ以上の頂点は「腕そのもの」とみなして触らない。
# 腕は下ろすと脇より低くなるので、高さだけで判定すると腕まで壊す。
LIMIT = float(a[4]) if len(a) > 4 else 0.35

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO+BL])
COMP = {5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}
def lay(i):
    ac = G['accessors'][i]; n = NUM[ac['type']]; f, s = COMP[ac['componentType']]
    bv = G['bufferViews'][ac['bufferView']]
    return ac, n, f, bv.get('byteOffset',0)+ac.get('byteOffset',0), bv.get('byteStride') or n*s
def rd(i):
    ac, n, f, b, st = lay(i)
    return np.array([struct.unpack_from('<'+f*n, bd, b+k*st) for k in range(ac['count'])], float)
def wr(i, arr):
    ac, n, f, b, st = lay(i)
    for k in range(ac['count']): struct.pack_into('<'+f*n, bd, b+k*st, *arr[k])

nodes = G['nodes']; parent = {}
for i, nd in enumerate(nodes):
    for c in nd.get('children', []): parent[c] = i
n2i = {nd.get('name',''): i for i, nd in enumerate(nodes)}
def q2m(q):
    x, y, z, w = q
    return np.array([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),
                     2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]).reshape(3,3)
def wpos(i):
    ch = []; j = i
    while j is not None: ch.append(j); j = parent.get(j)
    M = np.eye(4)
    for j in reversed(ch):
        nd = nodes[j]; L = np.eye(4)
        L[:3,:3] = q2m(np.array(nd.get('rotation',[0,0,0,1]),float))@np.diag(np.array(nd.get('scale',[1,1,1]),float))
        L[:3,3] = np.array(nd.get('translation',[0,0,0]),float); M = M@L
    return M[:3,3]

jn = [nodes[j].get('name') for j in G['skins'][0]['joints']]
ARM = {jn.index(n) for n in ['LeftArm','LeftForeArm','LeftHand','RightArm','RightForeArm','RightHand'] if n in jn}
BODY = [jn.index(n) for n in ['Spine02','Spine01','Spine','Hips'] if n in jn]
if ARMPIT is None:
    ARMPIT = min(wpos(n2i['LeftArm'])[1], wpos(n2i['RightArm'])[1]) - 0.03
print("AC 脇の高さ %.3f、そこから %.3f 下までなじませる" % (ARMPIT, FADE))

pr = G['meshes'][0]['primitives'][0]
P = rd(pr['attributes']['POSITION'])
J = rd(pr['attributes']['JOINTS_0']).astype(int)
W = rd(pr['attributes']['WEIGHTS_0'])
fixed = 0; moved = 0.0
for v in range(len(P)):
    y = P[v, 1]                                   # glTF は Y が上
    if y >= ARMPIT: continue
    aw = sum(W[v, k] for k in range(4) if J[v, k] in ARM)
    if aw >= LIMIT: continue          # 腕そのものの頂点は触らない
    t = min(1.0, (ARMPIT - y)/FADE)
    cut = t*t*(3-2*t)                             # 下へ行くほど強く外す
    take = 0.0
    for k in range(4):
        if J[v, k] in ARM and W[v, k] > 0:
            d = W[v, k]*cut; W[v, k] -= d; take += d
    if take <= 1e-6: continue
    slot = next((k for k in range(4) if J[v, k] in BODY), None)
    if slot is None:
        slot = int(np.argmin(W[v])); J[v, slot] = BODY[-1]; W[v, slot] = 0.0
    W[v, slot] += take
    s = W[v].sum()
    if s > 1e-6: W[v] /= s
    fixed += 1; moved = max(moved, take)
print("AC 直した頂点 %d 個、いちばん大きく外した重み %.2f" % (fixed, moved))
wr(pr['attributes']['WEIGHTS_0'], W); wr(pr['attributes']['JOINTS_0'], J)

js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += bytes((4-len(bn)%4)%4)
out = b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out)
print("AC 書き出し", DST)
