# -*- coding: utf-8 -*-
"""メガネの枠をポリゴンで後付けする。

   生成時にメガネを立体にすると顔が凹むので、顔はメガネ無しで作り、枠だけを
   あとから細い輪として足す。輪は顔の表面に沿わせ、表面から少し浮かせる。
   頭の骨（Head）に 100% 付けるので、頭と一緒に動く。

   足すもの：左右の輪、鼻の上の橋、耳へ向かう短いつる（髪に隠れる長さで止める）。
   同じメッシュに新しい面の束（primitive）として追加し、材質は赤の単色。
   UV は、テクスチャ上でメガネの赤い線が描かれている画素を指しておく。
   Unity 側の FaceBlink がどの材質にも顔の絵を貼ってしまうので、それでも赤く見えるようにするため。

   glTF ファイルの中は Y が上。引数は Blender 座標（Z が上）で受け取る。
   実行: blender -b --factory-startup -P addglasses.py -- 入力.glb 出力.glb 右目x,y,z 左目x,y,z 輪の半径 [線の太さ 既定0.004] [浮かせ 既定0.006]
"""
import json, struct, sys, math, os, tempfile, colorsys
import numpy as np
import bpy
from mathutils import kdtree, Vector

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
ER = [float(v) for v in a[2].split(',')]; EL = [float(v) for v in a[3].split(',')]
RING = float(a[4]); TUBE = float(a[5]) if len(a) > 5 else 0.004; LIFT = float(a[6]) if len(a) > 6 else 0.006

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
nodes = G['nodes']; parent = {}
for i, nd in enumerate(nodes):
    for c in nd.get('children', []): parent[c] = i
mesh_node = next(i for i, nd in enumerate(nodes) if 'mesh' in nd)
root = mesh_node
while root in parent: root = parent[root]
T = np.array(nodes[root].get('translation',[0,0,0]), float)
mesh = G['meshes'][nodes[mesh_node]['mesh']]; pr0 = mesh['primitives'][0]
P = rd(pr0['attributes']['POSITION']) + T                 # glTF 世界座標（メートル）
NRM0 = rd(pr0['attributes']['NORMAL'])
UV0 = rd(pr0['attributes']['TEXCOORD_0'])
jn = [nodes[j].get('name') for j in G['skins'][0]['joints']]
HEAD = jn.index('Head')

def b2g(v): return np.array([v[0], v[2], -v[1]])            # Blender(x,y,z) → glTF(x, z, -y)
er = b2g(ER); el = b2g(EL)

# 顔の頂点（目の高さの前側）で木を作り、輪の各点を表面へ寄せる
face = np.where((np.abs(P[:,0]) < 0.25) & (P[:,2] > 0.05) & (np.abs(P[:,1] - er[1]) < 0.20))[0]
kd = kdtree.KDTree(len(face))
for k, vi in enumerate(face): kd.insert(Vector(P[vi]), k)
kd.balance()
def on_surface(q):
    """点 q に一番近い顔の表面点を返し、そこから面の向き（法線）に LIFT だけ浮かせる。
       前（+z）へ浮かせるだけだと、顔の横へ回り込んだ所で輪が肌に埋まる。"""
    hits = kd.find_n(Vector(q), 12)
    c = np.mean([np.array(h[0]) for h in hits], axis=0)
    n = np.mean([NRM0[face[h[1]]] for h in hits], axis=0); n /= max(1e-9, np.linalg.norm(n))
    return c + n*LIFT

# メガネの赤い線の画素の UV を一つ探す（テクスチャが貼られても赤く見えるように）
img0 = G['images'][0]; bv = G['bufferViews'][img0['bufferView']]
tmp = os.path.join(tempfile.gettempdir(), "_ag_tex.png")
open(tmp,'wb').write(bytes(bd[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']]))
im = bpy.data.images.load(tmp); IW, IH = im.size
PIX = np.array(im.pixels[:], dtype=np.float32).reshape(IH, IW, 4)
red_uv = None
for vi in face:
    u, v = UV0[vi]; px = min(IW-1, int(u*IW)); py = min(IH-1, int((1-v)*IH))
    r, g, b = PIX[py, px, :3]; h, s, vv = colorsys.rgb_to_hsv(float(r), float(g), float(b))
    if s > 0.5 and vv > 0.45 and (h < 0.04 or h > 0.94):
        red_uv = (float(u), float(v)); break
if red_uv is None:
    red_uv = (0.0, 0.0); print("AG 【注意】赤い画素が見つからないので UV は (0,0)")
print("AG 赤い画素の UV", red_uv)

# ---- 管を作る：中心線の点列 → 断面 8 角形 ----
SEG = 8
verts = []; norms = []; tris = []
def tube(path, closed):
    base = len(verts)
    n = len(path)
    for i, c in enumerate(path):
        nxt = path[(i+1) % n] if closed else path[min(i+1, n-1)]
        prv = path[(i-1) % n] if closed else path[max(i-1, 0)]
        t = nxt - prv; t = t / max(1e-9, np.linalg.norm(t))
        up = np.array([0, 1.0, 0]) if abs(t[1]) < 0.9 else np.array([1.0, 0, 0])
        u = np.cross(t, up); u /= np.linalg.norm(u); w = np.cross(t, u)
        for k in range(SEG):
            th = 2*math.pi*k/SEG; nrm = math.cos(th)*u + math.sin(th)*w
            verts.append(c + TUBE*nrm); norms.append(nrm)
    m = n if closed else n-1
    for i in range(m):
        i2 = (i+1) % n
        for k in range(SEG):
            k2 = (k+1) % SEG
            a0 = base + i*SEG + k; a1 = base + i*SEG + k2; b0 = base + i2*SEG + k; b1 = base + i2*SEG + k2
            tris.extend([a0, b0, a1, a1, b0, b1])

for cen, sign in ((er, -1), (el, 1)):
    ring = [on_surface(np.array([cen[0] + RING*math.cos(t), cen[1] + RING*math.sin(t), cen[2]]))
            for t in np.linspace(0, 2*math.pi, 40, endpoint=False)]
    tube(ring, True)
# 橋：右輪の内側から左輪の内側へ
bridge = [on_surface(np.array([x, (er[1]+el[1])/2 + 0.004, er[2]])) for x in np.linspace(er[0]+RING*0.9, el[0]-RING*0.9, 6)]
tube(bridge, False)
# つる：輪の外側から、頭の横へ 3.5cm 後ろへ（髪に隠れる）
for cen, sign in ((er, -1), (el, 1)):
    start = on_surface(np.array([cen[0] + sign*RING, cen[1] + 0.004, cen[2]]))
    path = [start + np.array([sign*0.010*k/4, 0.0, -0.035*k/4]) for k in range(5)]
    tube(path, False)
V = np.array(verts, np.float32) - T; N = np.array(norms, np.float32); I = np.array(tris, np.uint32)
print("AG 頂点 %d、三角形 %d" % (len(V), len(I)//3))

# ---- glb に足す ----
def add_view(data, target):
    while len(bd) % 4: bd.append(0)
    off = len(bd); bd.extend(data)
    view = {'buffer':0, 'byteOffset':off, 'byteLength':len(data)}
    if target: view['target'] = target
    G['bufferViews'].append(view)
    return len(G['bufferViews'])-1
def add_acc(view, ctype, count, atype, mn=None, mx=None):
    ac = {'bufferView':view, 'componentType':ctype, 'count':count, 'type':atype}
    if mn is not None: ac['min'] = mn; ac['max'] = mx
    G['accessors'].append(ac); return len(G['accessors'])-1
nv = len(V)
a_pos = add_acc(add_view(V.astype('<f4').tobytes(), 34962), 5126, nv, 'VEC3', [float(x) for x in V.min(0)], [float(x) for x in V.max(0)])
a_nrm = add_acc(add_view(N.astype('<f4').tobytes(), 34962), 5126, nv, 'VEC3')
UV = np.tile(np.array(red_uv, '<f4'), (nv, 1))
a_uv = add_acc(add_view(UV.astype('<f4').tobytes(), 34962), 5126, nv, 'VEC2')
JJ = np.zeros((nv, 4), np.uint8); JJ[:,0] = HEAD
a_j = add_acc(add_view(JJ.tobytes(), 34962), 5121, nv, 'VEC4')
WW = np.zeros((nv, 4), '<f4'); WW[:,0] = 1.0
a_w = add_acc(add_view(WW.tobytes(), 34962), 5126, nv, 'VEC4')
a_idx = add_acc(add_view(I.astype('<u4').tobytes(), 34963), 5125, len(I), 'SCALAR')
G.setdefault('materials', []).append({'name':'glasses', 'pbrMetallicRoughness':{'baseColorFactor':[0.92,0.16,0.16,1.0],'metallicFactor':0.0,'roughnessFactor':0.6}})
mesh['primitives'].append({'attributes':{'POSITION':a_pos,'NORMAL':a_nrm,'TEXCOORD_0':a_uv,'JOINTS_0':a_j,'WEIGHTS_0':a_w},
                           'indices':a_idx, 'material':len(G['materials'])-1, 'mode':4})
G['buffers'][0]['byteLength'] = len(bd)
js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = (b'glTF' + struct.pack('<II',2,12+8+len(js)+8+len(bn)) + struct.pack('<II',len(js),0x4E4F534A) + js
       + struct.pack('<II',len(bn),0x004E4942) + bn)
open(DST,'wb').write(out); print("AG 書き出し", DST)
