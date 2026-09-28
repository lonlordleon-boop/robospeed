# -*- coding: utf-8 -*-
"""のっぺらぼうの顔に、生成が勝手に彫り込んだ目・口の凹凸を消す。
   顔の前面になめらかな2次曲面 z = f(x, y) を当てはめ、肌の頂点をその面へ寄せる。
   ・動かすのは箱の中の「肌」の頂点だけ（テクスチャの明るさで判定。前髪は暗いので動かない）
   ・目のくぼみは曲面より奥にある点なので、1回当てはめたあと大きく奥にある点を除いて当て直す
   ・箱の縁に向かって寄せる量を 0 にしていく（縁で筋が出ないように）
   ・動かすのは前後（Z）だけ。法線は、動いた頂点のまわりだけ計算し直す
   meshsmooth.py の箱ならしは、形を痩せさせない方式なので目のくぼみが消えず、箱の縁に筋が出た（芸術少女・わんぱく少女）。

   座標は glTF（X 左右・Y 上・Z 前）。
   箱は目より十分広く取ること（縁の 25% は弱めて寄せるので、目の縁が箱の縁近くにあると残る）。
   前髪は暗いので箱に入っても動かない。耳は顔の前面より奥にあるので Z の範囲で外す。
   実行: blender -b --factory-startup -P facefit.py -- 入力.glb 出力.glb x0,x1,y0,y1,z0,z1 [明るさのしきい値 0.55] [次数 3]"""
import bpy, json, struct, sys, os, tempfile
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
X0, X1, Y0, Y1, Z0, Z1 = [float(v) for v in a[2].split(',')]
LUM = float(a[3]) if len(a) > 3 else 0.55
ORDER = int(a[4]) if len(a) > 4 else 3     # 曲面の次数。2次だとあごの丸みを表せず、あごの上がへこんだ（わんぱく少女）

raw = open(SRC,'rb').read(); off=12; ck=[]
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t:(o,l) for t,o,l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO+BL])
COMP = {5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
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

cands = [(G['accessors'][m['primitives'][0]['attributes']['POSITION']]['count'], i) for i, m in enumerate(G['meshes']) if 'JOINTS_0' in m['primitives'][0]['attributes']]
pr = G['meshes'][max(cands)[1]]['primitives'][0]
P = rd(pr['attributes']['POSITION']); N = rd(pr['attributes']['NORMAL']); UV = rd(pr['attributes']['TEXCOORD_0'])
idx = rd(pr['indices']).astype(int).ravel()

# 絵を読んで、頂点ごとの明るさを取る
mat = G['materials'][pr['material']]
ti = mat['pbrMetallicRoughness']['baseColorTexture']['index']
img = G['images'][G['textures'][ti]['source']]
bv = G['bufferViews'][img['bufferView']]; ib = bytes(bd[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']])
ext = '.png' if img.get('mimeType','').endswith('png') else '.jpg'
tmp = os.path.join(tempfile.gettempdir(), 'facefit_tex' + ext); open(tmp,'wb').write(ib)
im = bpy.data.images.load(tmp); W, H = im.size
A = np.array(im.pixels[:], dtype=np.float32).reshape(H, W, 4)
px = np.clip((UV[:,0] % 1.0) * W, 0, W-1).astype(int); py = np.clip((1.0 - (UV[:,1] % 1.0)) * H, 0, H-1).astype(int)
lum = A[py, px, :3].mean(1)
lum = np.where(lum <= 0.0031308, lum * 12.92, 1.055 * np.maximum(lum, 0) ** (1/2.4) - 0.055)   # sRGB の明るさ

inbox = (P[:,0] >= X0) & (P[:,0] <= X1) & (P[:,1] >= Y0) & (P[:,1] <= Y1) & (P[:,2] >= Z0) & (P[:,2] <= Z1)
skin = inbox & (lum > LUM) & (N[:,2] > 0.15)
print("FF 箱の中 %d 頂点、そのうち肌 %d" % (inbox.sum(), skin.sum()))
def basis(x, y):
    cols = [x**i * y**j for i in range(ORDER + 1) for j in range(ORDER + 1 - i)]
    return np.stack(cols, 1)
X, Y, Z = P[skin,0], P[skin,1], P[skin,2]
c, *_ = np.linalg.lstsq(basis(X, Y), Z, rcond=None)
r = Z - basis(X, Y) @ c
keep = r > -1.5 * np.std(r)          # 奥にへこんだ点（目のくぼみ）を除いて当て直す
c, *_ = np.linalg.lstsq(basis(X[keep], Y[keep]), Z[keep], rcond=None)
fit = basis(P[:,0], P[:,1]) @ c
d = fit - P[:,2]
print("FF 曲面からのずれ（肌）: 平均 %.4f  奥へ最大 %.4f  手前へ最大 %.4f" % (np.abs(d[skin]).mean(), d[skin].max(), -d[skin].min()))
# 箱の縁で 0、内側 25% より中で 1
def edge(v, lo, hi):
    t = np.minimum(v - lo, hi - v) / (0.25 * (hi - lo)); t = np.clip(t, 0, 1); return t*t*(3-2*t)
wgt = np.where(skin, edge(P[:,0], X0, X1) * edge(P[:,1], Y0, Y1), 0.0)
# 同じ位置の頂点（UV の継ぎ目で分かれたもの）は、必ず同じだけ動かす。
# 肌かどうかを頂点ごとの絵の明るさで決めるので、継ぎ目の片方だけが肌と判定されて動き、
# 顔にすき間が開いた（わんぱく少女で最大 39mm、芸術少女で 20mm）。
# すき間から奥の髪が見えて目の高さに細い線が出て、光を当てると顔がでこぼこに見えた
gkey = np.round(P / 1e-5).astype(np.int64)
_, gid = np.unique(gkey, axis=0, return_inverse=True); gid = gid.ravel()
gmax = np.zeros(gid.max() + 1); np.maximum.at(gmax, gid, wgt)
wgt = gmax[gid]
P2 = P.copy(); P2[:,2] = P[:,2] + wgt * d
moved = wgt > 1e-4
print("FF 動かした頂点 %d  動いた量 平均 %.4f  最大 %.4f" % (moved.sum(), np.abs(wgt*d)[moved].mean(), np.abs(wgt*d).max()))
wr(pr['attributes']['POSITION'], P2)
acp = G['accessors'][pr['attributes']['POSITION']]; acp['min'] = P2.min(0).tolist(); acp['max'] = P2.max(0).tolist()

# 法線：同じ位置の頂点をまとめて、面の法線を足し合わせる。動いた頂点のまわりだけ書き換える
key = np.round(P / 1e-5).astype(np.int64)
_, grp = np.unique(key, axis=0, return_inverse=True); grp = grp.ravel()
tri = idx.reshape(-1, 3)
fn = np.cross(P2[tri[:,1]] - P2[tri[:,0]], P2[tri[:,2]] - P2[tri[:,0]])
acc = np.zeros((grp.max()+1, 3))
for k in range(3): np.add.at(acc, grp[tri[:,k]], fn)
ln = np.linalg.norm(acc, axis=1); ln[ln < 1e-12] = 1
NN = acc[grp] / ln[grp][:, None]
touched = np.zeros(len(P), bool)
mt = moved[tri].any(1)
for k in range(3): touched[tri[mt, k]] = True
touched = np.isin(grp, np.unique(grp[touched]))
N2 = np.where(touched[:, None], NN, N)
wr(pr['attributes']['NORMAL'], N2)
print("FF 法線を計算し直した頂点 %d" % touched.sum())

js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out)
print("FF 書き出し", DST)
