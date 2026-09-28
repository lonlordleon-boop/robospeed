# -*- coding: utf-8 -*-
"""骨の向きを指定して、短いループのアニメを1本作る（「はい！」の挙手など）。
   骨ごとに「その骨をどの向きに向けたいか」を世界の座標で指定する。
   「骨:x,y,z@角度」と書くと、向けたあとその向きを軸にひねる（手のひらの向きを決めるのに使う）。
   「骨:rx,y,z@角度」と書くと、向きは変えずにその軸のまわりに回すだけ。
   手首のように先に骨が無いところは、向きを計算できないのでこちらを使う。
   いまの向きから指定の向きへ回す最小の回転を求め、親の座標系に移して焼き込む。
   全部の骨に回転のカーブを書くので、他のクリップの残りが混ざることはない。
   腰を上下させる小さな弾みも付けられる。
   向きは Blender の座標（Z が上、キャラは -Y を向いている）で書く。
   土台のクリップを指定すると、その1コマ目の姿勢を立ち姿の基準にする（Idle を指定するのが普通）。
   glb の節点に入っている回転は自然な立ち姿とは限らず、そのままだと腕が横に開く。
   実行: blender -b --factory-startup --python makepose.py -- 入力.glb 出力.glb クリップ名 長さ秒 コマ数 "骨:x,y,z;..." [弾みの高さ] [弾みの回数] ["骨:角度,骨:角度"] [土台のクリップ]"""
import json, struct, sys, math
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, NAME = a[0], a[1], a[2]
DUR, NF = float(a[3]), int(a[4])
SPEC = a[5]
BOUNCE = float(a[6]) if len(a) > 6 else 0.0
NBOUNCE = float(a[7]) if len(a) > 7 else 2.0
SHAKE = a[8] if len(a) > 8 else None
BASECLIP = a[9] if len(a) > 9 else None

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO+BL])

nodes = G['nodes']; parent = {}
for i, nd in enumerate(nodes):
    for c in nd.get('children', []): parent[c] = i
n2i = {nd.get('name',''): i for i, nd in enumerate(nodes)}
joints = G['skins'][0]['joints']

def q2m(q):
    x, y, z, w = q
    return np.array([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),
                     2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]).reshape(3,3)
def qmul(a_, b_):
    ax, ay, az, aw = a_; bx, by, bz, bw = b_
    return np.array([aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx,
                     aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz])
def qconj(q): return np.array([-q[0], -q[1], -q[2], q[3]])
def qaxis(ax, deg):
    ax = np.array(ax, float); n = np.linalg.norm(ax)
    if n < 1e-9: return np.array([0,0,0,1.0])
    ax = ax/n; h = math.radians(deg)/2.0
    return np.array([ax[0]*math.sin(h), ax[1]*math.sin(h), ax[2]*math.sin(h), math.cos(h)])
# いま組み立て中の姿勢。上腕を回したら、前腕の計算はその結果を見て行う必要がある。
# 素の姿勢のまま計算すると、親の回転ぶんだけ子の向きがずれる。
cur = {i: np.array(nd.get('rotation',[0,0,0,1]), float) for i, nd in enumerate(nodes)}
base_t = {}

# 土台にするクリップの1コマ目を、立ち姿の基準にする。
# glb の節点に入っている回転は必ずしも自然な立ち姿ではなく、
# そのまま使うと腕が横に開いた姿勢になる。
def read_acc(i):
    ac = G['accessors'][i]; n = {'SCALAR':1,'VEC3':3,'VEC4':4}[ac['type']]
    bv = G['bufferViews'][ac['bufferView']]
    b = bv.get('byteOffset',0)+ac.get('byteOffset',0); st = bv.get('byteStride') or n*4
    return np.array([struct.unpack_from('<'+'f'*n, bd, b+k*st) for k in range(ac['count'])], float)
if BASECLIP:
    bc = next((x for x in G['animations'] if x.get('name') == BASECLIP), None)
    if bc is None:
        print("MP 土台のクリップが無い", BASECLIP); sys.exit(1)
    for chn in bc['channels']:
        tgt = chn['target']; smp = bc['samplers'][chn['sampler']]
        v = read_acc(smp['output'])
        if tgt['path'] == 'rotation': cur[tgt['node']] = v[0]/np.linalg.norm(v[0])
        elif tgt['path'] == 'translation': base_t[tgt['node']] = v[0]
    print("MP %s の1コマ目を土台にした" % BASECLIP)
def worldM(i):
    ch = []; j = i
    while j is not None: ch.append(j); j = parent.get(j)
    M = np.eye(4)
    for j in reversed(ch):
        nd = nodes[j]; L = np.eye(4)
        L[:3,:3] = q2m(cur[j])@np.diag(np.array(nd.get('scale',[1,1,1]),float))
        L[:3,3] = np.array(nd.get('translation',[0,0,0]),float); M = M@L
    return M
def worldQ(i):
    q = np.array([0,0,0,1.0]); ch = []; j = i
    while j is not None: ch.append(j); j = parent.get(j)
    for j in reversed(ch): q = qmul(q, cur[j])
    return q

# glTF は Y が上、Blender は Z が上。指定は Blender で書いてもらう
def to_gltf(v): return np.array([v[0], v[2], -v[1]], float)

def child_of(i):
    for c in nodes[i].get('children', []):
        if c in joints: return c
    return None

# --- 指定された骨の回転を求める ---
delta = {}
for part in SPEC.split(';'):
    if not part.strip(): continue
    bone, vec = part.split(':')
    roll = 0.0
    if '@' in vec:                      # 「向き@ひねり角度」で、骨を自分の軸まわりにひねれる
        vec, r = vec.split('@'); roll = float(r)
    i = n2i[bone.strip()]
    if vec.strip().startswith('r'):
        # 「骨:rx,y,z@角度」＝その軸のまわりに回すだけ。
        # 手首のように先の骨が無いところは、向きを指定できないのでこちらを使う。
        ax = to_gltf([float(x) for x in vec.strip()[1:].split(',')])
        W = qaxis(ax, roll)
        Rp = worldQ(parent[i])
        d = qmul(qmul(qconj(Rp), W), Rp)
        cur[i] = qmul(d, cur[i]); delta[i] = d
        print("MP %s を軸まわりに %+.1f 度 回す" % (bone, roll))
        continue
    c = child_of(i)
    if c is None: print("MP 子の骨が無い", bone); continue
    d0 = worldM(c)[:3,3] - worldM(i)[:3,3]
    d0 = d0/np.linalg.norm(d0)
    d1 = to_gltf([float(x) for x in vec.split(',')])
    d1 = d1/np.linalg.norm(d1)
    ax = np.cross(d0, d1); s = np.linalg.norm(ax)
    ang = math.degrees(math.atan2(s, float(np.dot(d0, d1))))
    W = qaxis(ax, ang) if s > 1e-9 else np.array([0,0,0,1.0])
    if roll != 0.0:
        W = qmul(qaxis(d1, roll), W)    # 向けたあと、その向きを軸にひねる
    Rp = worldQ(parent[i])
    d = qmul(qmul(qconj(Rp), W), Rp)
    cur[i] = qmul(d, cur[i])           # ここで反映してから、次の骨を計算する
    delta[i] = d
    print("MP %s を %.1f 度 回す%s" % (bone, ang, ("（ひねり %+.0f 度）" % roll) if roll else ""))

# 揺らす骨は「骨:角度,骨:角度」でいくつでも書ける。腕全体を大きく振るときに使う。
# 揺らす骨は「骨:角度」または「骨:角度:軸」。軸は fwd(前後) up(上下) side(左右) から選ぶ。
# 腕を下げて前腕を前へ向けた姿勢では、左右に振るための軸は up になる。
AXES = {'fwd': (0.0, 0.0, 1.0), 'up': (0.0, 1.0, 0.0), 'side': (1.0, 0.0, 0.0)}
shakes = {}
if SHAKE:
    for part in SHAKE.split(','):
        if not part.strip(): continue
        f = part.split(':')
        b, d = f[0], float(f[1]); axn = f[2] if len(f) > 2 else 'fwd'
        shakes[n2i[b.strip()]] = (d, np.array(AXES[axn], float))
        print("MP %s を ±%.1f 度 揺らす（軸 %s）" % (b, d, axn))

# --- カーブを作る ---
def new_accessor(arr, typ, mn=None, mx=None):
    global bd
    while len(bd) % 4 != 0: bd += bytes(1)
    o = len(bd); buf = bytearray()
    for row in np.atleast_2d(arr): buf += struct.pack('<'+'f'*len(row), *row)
    bd += buf
    G['bufferViews'].append({'buffer': 0, 'byteOffset': o, 'byteLength': len(buf)})
    ac = {'bufferView': len(G['bufferViews'])-1, 'componentType': 5126,
          'count': len(np.atleast_2d(arr)), 'type': typ}
    if mn is not None: ac['min'] = mn; ac['max'] = mx
    G['accessors'].append(ac)
    return len(G['accessors'])-1

T = np.linspace(0.0, DUR, NF+1)[:, None]     # 最後のコマは最初と同じ姿勢にして輪にする
ti = new_accessor(T, 'SCALAR', [float(T.min())], [float(T.max())])

samplers = []; channels = []
fwd = np.array([0.0, 0.0, 1.0])              # glTF の前向き（頭の目印から求めた値と同じ）
for j in joints:
    base = cur[j]
    rows = []
    for k in range(NF+1):
        q = base
        if j in shakes:
            shake_deg, shake_ax = shakes[j]
            ph = 2*math.pi*(k/NF)*NBOUNCE
            Rp = worldQ(parent[j])
            W = qaxis(shake_ax, shake_deg*math.sin(ph))
            q = qmul(qmul(qmul(qconj(Rp), W), Rp), base)
        rows.append(q/np.linalg.norm(q))
    oi = new_accessor(np.array(rows), 'VEC4')
    samplers.append({'input': ti, 'output': oi, 'interpolation': 'LINEAR'})
    channels.append({'sampler': len(samplers)-1, 'target': {'node': j, 'path': 'rotation'}})

if BOUNCE != 0.0:
    hips = n2i['Hips']
    t0 = base_t.get(hips, np.array(nodes[hips].get('translation', [0,0,0]), float))
    rows = []
    for k in range(NF+1):
        ph = 2*math.pi*(k/NF)*NBOUNCE
        v = t0.copy(); v[1] += BOUNCE*(0.5-0.5*math.cos(ph))   # 下から上へ、輪になる
        rows.append(v)
    oi = new_accessor(np.array(rows), 'VEC3')
    samplers.append({'input': ti, 'output': oi, 'interpolation': 'LINEAR'})
    channels.append({'sampler': len(samplers)-1, 'target': {'node': hips, 'path': 'translation'}})
    print("MP 腰を %.3f 上下させる（%.0f 回）" % (BOUNCE, NBOUNCE))

old = next((x for x in G['animations'] if x.get('name') == NAME), None)
if old is not None: G['animations'].remove(old)
G['animations'].append({'name': NAME, 'channels': channels, 'samplers': samplers})
G['buffers'][0]['byteLength'] = len(bd)
print("MP クリップ %s を作った（%.2f 秒、%d コマ、カーブ %d 本）" % (NAME, DUR, NF+1, len(channels)))

js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += bytes((4-len(bn)%4)%4)
out = b'glTF'+struct.pack('<II', 2, 12+8+len(js)+8+len(bn))
out += struct.pack('<II', len(js), 0x4E4F534A)+js+struct.pack('<II', len(bn), 0x004E4942)+bn
open(DST, 'wb').write(out)
print("MP 書き出し", DST)
