# -*- coding: utf-8 -*-
"""アニメの動きの大きさを変える。
   各コマの姿勢を「そのクリップの平均の姿勢」へ寄せることで、振りの大きさだけを小さくする。
   回転は平均からの差を軸と角度に直し、角度に倍率を掛ける。位置は平均からの差に倍率を掛ける。
   平均そのものは動かさないので、立ち方や向きは変わらない。
   元のクリップは壊さない。新しい入れ物（アクセサ）を作って書き込むので、
   たとえばスキップを小さくして歩きに入れても、スキップ自体はそのまま残る。
   実行: blender -b --factory-startup --python scaleclip.py -- 入力.glb 出力.glb 元クリップ 倍率 [入れ先クリップ]
   入れ先を書くと、そのクリップの中身を差し替える（名前は入れ先のまま）。書かないと新しいクリップを足す。"""
import json, struct, sys, math
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, CLIP, K = a[0], a[1], a[2], float(a[3])
INTO = a[4] if len(a) > 4 else None

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

def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return np.array([aw*bx+ax*bw+ay*bz-az*by,
                     aw*by-ax*bz+ay*bw+az*bx,
                     aw*bz+ax*by-ay*bx+az*bw,
                     aw*bw-ax*bx-ay*by-az*bz])
def qconj(q): return np.array([-q[0], -q[1], -q[2], q[3]])
def qscale(q, k):
    """回転の角度だけを k 倍にする（軸はそのまま）"""
    q = q/np.linalg.norm(q)
    w = max(-1.0, min(1.0, q[3]))
    ang = 2.0*math.acos(w)
    s = math.sqrt(max(0.0, 1.0-w*w))
    if s < 1e-8 or ang < 1e-8: return np.array([0, 0, 0, 1.0])
    ax = q[:3]/s
    h = (ang*k)/2.0
    return np.array([ax[0]*math.sin(h), ax[1]*math.sin(h), ax[2]*math.sin(h), math.cos(h)])
def qmean(V):
    """符号をそろえて平均し、正規化する"""
    ref = V[0]; acc = np.zeros(4)
    for q in V: acc += q if np.dot(q, ref) >= 0 else -q
    n = np.linalg.norm(acc)
    return acc/n if n > 1e-9 else np.array([0, 0, 0, 1.0])

src = next((x for x in G['animations'] if x.get('name') == CLIP), None)
if src is None:
    print("SC クリップが無い", CLIP); sys.exit(1)

def new_accessor(arr, typ):
    """新しい入れ物を作って値を書き込み、その番号を返す"""
    global bd
    while len(bd) % 4 != 0: bd += bytes(1)
    off = len(bd)
    buf = bytearray()
    for row in arr: buf += struct.pack('<'+'f'*len(row), *row)
    bd += buf
    G['bufferViews'].append({'buffer': 0, 'byteOffset': off, 'byteLength': len(buf)})
    G['accessors'].append({'bufferView': len(G['bufferViews'])-1, 'componentType': 5126,
                           'count': len(arr), 'type': typ})
    return len(G['accessors'])-1

new_samplers = []; new_channels = []; changed = 0
for chn in src['channels']:
    path = chn['target']['path']
    smp = src['samplers'][chn['sampler']]
    v = rd(smp['output'])
    if path == 'rotation':
        m = qmean(v); out = v.copy()
        for i in range(len(v)):
            q = v[i] if np.dot(v[i], m) >= 0 else -v[i]
            d = qmul(qconj(m), q)              # 平均からの差
            out[i] = qmul(m, qscale(d, K))     # 差を K 倍して戻す
            out[i] /= np.linalg.norm(out[i])
        oi = new_accessor(out, 'VEC4'); changed += 1
    elif path == 'translation':
        m = v.mean(0)
        oi = new_accessor(m + (v - m)*K, 'VEC3'); changed += 1
    else:
        oi = smp['output']                     # 大きさのカーブはそのまま使う
    new_samplers.append({'input': smp['input'], 'output': oi,
                         'interpolation': smp.get('interpolation', 'LINEAR')})
    new_channels.append({'sampler': len(new_samplers)-1, 'target': dict(chn['target'])})
print("SC %s を %.2f 倍にした（作ったカーブ %d 本）" % (CLIP, K, changed))

dst = next((x for x in G['animations'] if x.get('name') == INTO), None) if INTO else None
if INTO is not None and dst is None:
    print("SC 入れ先が無い", INTO); sys.exit(1)
if dst is None:
    dst = {'name': "%s_x%.2f" % (CLIP, K)}
    G['animations'].append(dst)
dst['channels'] = new_channels
dst['samplers'] = new_samplers
print("SC %s に入れた" % dst.get('name'))
G['buffers'][0]['byteLength'] = len(bd)

js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += bytes((4-len(bn)%4)%4)
out = b'glTF'+struct.pack('<II', 2, 12+8+len(js)+8+len(bn))
out += struct.pack('<II', len(js), 0x4E4F534A)+js+struct.pack('<II', len(bn), 0x004E4942)+bn
open(DST, 'wb').write(out)
print("SC 書き出し", DST)
