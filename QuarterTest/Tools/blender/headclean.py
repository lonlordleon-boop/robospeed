# -*- coding: utf-8 -*-
"""首の関節より上にある頂点から、肩・腕・背骨・腰の重みを完全に外し、頭と首だけで動かす。

   自動リグが顔や髪を「肩の一部」と判断していると、歩くたびに肩の動きが顔へ伝わり、
   顔がぐにゃぐにゃ揺れる。hairfix.py は頭の重みが 0.2 以上の頂点しか直さないので、
   肩の重みのほうが濃い頂点はそのまま残る。この道具はそれを断ち切る。

   残すのは Head・headfront・neck の三つだけ。三つとも重みが無い頂点は Head に寄せる。
   glTF ファイルの中は Y が上。

   「対象の種類」を書くと、その材質の網だけを直す。材質名「種類:名前」の種類で選ぶ。
   服の襟は首の関節より上まで伸びているので、まとめて直すと襟が頭に付いてきてしまう。
   種類の付いていない材質（素体）は「body」として扱う。

   「ならしの幅」を書くと、切り替えを段々にする。首の高さで一気に肩の重みを0にすると、
   その線を境に面がねじれて、素体だけで見たときに首に筋が出る。幅のぶん少しずつ減らせば出ない。

   実行: blender -b --factory-startup -P headclean.py --
         入力.glb 出力.glb [首からの余裕(m) 既定0.00] [対象の種類,... 既定すべて] [ならしの幅(m) 既定0]
"""
import json, struct, sys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
MARGIN = float(a[2]) if len(a) > 2 else 0.00
ONLY = a[3].split(',') if len(a) > 3 and a[3] else None
BLEND = float(a[4]) if len(a) > 4 else 0.0

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
KEEP = {i for i, n in enumerate(jn) if n in ('Head', 'headfront', 'neck')}
HEAD = jn.index('Head')
necky = wpos(n2i['neck'])[1]
print("HK 首の関節の高さ %.3f、そこから %.3f 上を頭として扱う" % (necky, MARGIN))

tot = 0; moved = {}
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        mat = G['materials'][pr['material']].get('name', '') if 'material' in pr else ''
        kind = mat.split(':')[0] if ':' in mat else 'body'
        if ONLY is not None and kind not in ONLY:
            print("HK %-18s（種類 %s）は対象外" % (mat[:18], kind)); continue
        print("HK %-18s（種類 %s）を直す" % (mat[:18], kind))
        P = rd(pr['attributes']['POSITION'])
        J = rd(pr['attributes']['JOINTS_0']).astype(int)
        W = rd(pr['attributes']['WEIGHTS_0'])
        for vi in range(len(P)):
            if P[vi,1] < necky + MARGIN: continue
            other = sum(W[vi,k] for k in range(4) if J[vi,k] not in KEEP and W[vi,k] > 0)
            if other <= 1e-6: continue
            # ならしの幅のぶん、上へ行くほど肩の重みを薄くする。幅0なら今までどおり一気に0
            t = 1.0
            if BLEND > 0:
                t = min(1.0, (P[vi,1] - (necky + MARGIN)) / BLEND)
                if t <= 0: continue
            for k in range(4):
                if J[vi,k] not in KEEP and W[vi,k] > 0:
                    moved[jn[J[vi,k]]] = moved.get(jn[J[vi,k]], 0) + 1
                    W[vi,k] *= (1.0 - t)
            s = W[vi].sum()
            if s <= 1e-6:                      # 頭も首も無かった頂点は、頭だけにする
                W[vi] = 0.0; J[vi,0] = HEAD; W[vi,0] = 1.0
            else:
                W[vi] /= s
            tot += 1
        wr(pr['attributes']['WEIGHTS_0'], W); wr(pr['attributes']['JOINTS_0'], J)
print("HK 直した頂点 %d 個  外した重みの元: %s" % (tot, sorted(moved.items(), key=lambda x: -x[1])))

G['buffers'][0]['byteLength'] = len(bd)
js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = (b'glTF' + struct.pack('<II',2,12+8+len(js)+8+len(bn))
       + struct.pack('<II',len(js),0x4E4F534A) + js
       + struct.pack('<II',len(bn),0x004E4942) + bn)
open(DST,'wb').write(out); print("HK 書き出し", DST)
