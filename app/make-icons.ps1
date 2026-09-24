# =========================================================================
# アイコンを一式そろえる（仕様書 14-4）
# =========================================================================
#
# ■ 何を作るか
#   1. アダプティブアイコンの前景  … 透過のまま。地色は Android が下に敷く
#   2. 旧式のアイコン（四角・丸）  … 地色を焼き込んだもの。古い端末はこちらを使う
#   3. Play ストア用 512×512       … **透過は不可。**必ず不透明にする
#
# ■ 絵の出どころ
#   docs/mecha/game/h6_red.png（ピュアカラー・赤）の **頭部だけ**を切り出す。
#   全身だと 48px まで縮んだとき何が描いてあるか分からなくなる。
#   顔なら、角と金のバイザーの形が残る（実機の見比べで決めた）。
#
# ■ 安全領域
#   アダプティブアイコンは 108dp の絵のうち **内側 72dp しか見えない**（66.7%）。
#   端末の形（丸・角丸・しずく）で外側が削られるため。
#   ここでは 64% に収めて、どの形でも角が切れないようにしている。
#
#   使いかた:  powershell -ExecutionPolicy Bypass -File make-icons.ps1
# =========================================================================

Add-Type -AssemblyName System.Drawing

$src  = "D:\unity-box\docs\mecha\game\h6_red.png"
$res  = "D:\unity-box\app\android\app\src\main\res"
$play = "D:\unity-box\app\store"

# 地色「鋼」。格納庫の金属の色。赤がいちばん締まって見える（実機で見比べた）
$BG = [System.Drawing.Color]::FromArgb(255, 43, 50, 56)

# 頭部の切り出し範囲（元絵 448x512 の中の座標）。角の先まで入れてある
$CX = 129; $CY = 6; $CW = 190; $CH = 190

$bmp = [System.Drawing.Bitmap]::FromFile($src)

function New-Icon {
    param([int]$Size, [bool]$Opaque, [double]$Fill, [bool]$Round)

    $ic = New-Object System.Drawing.Bitmap $Size, $Size
    $g  = [System.Drawing.Graphics]::FromImage($ic)
    $g.InterpolationMode = "HighQualityBicubic"
    $g.SmoothingMode     = "AntiAlias"

    if ($Opaque) {
        if ($Round) {
            # 丸いアイコンは **地色も丸く塗る。** 四角く塗ると角が残る
            $g.Clear([System.Drawing.Color]::Transparent)
            $br = New-Object System.Drawing.SolidBrush $BG
            $g.FillEllipse($br, 0, 0, $Size - 1, $Size - 1)
            $br.Dispose()
        } else {
            $g.Clear($BG)
        }
    } else {
        $g.Clear([System.Drawing.Color]::Transparent)
    }

    $w = [int]($Size * $Fill)
    $off = [int](($Size - $w) / 2)
    $g.DrawImage($bmp, (New-Object System.Drawing.Rectangle $off, $off, $w, $w), $CX, $CY, $CW, $CH, "Pixel")
    $g.Dispose()
    return $ic
}

function Save-Icon {
    param($Bitmap, [string]$Path)
    $dir = Split-Path $Path
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $Bitmap.Dispose()
}

# ---- 端末用 ----
# 旧式は 48dp、アダプティブの前景は 108dp。密度ごとの倍率は 1 / 1.5 / 2 / 3 / 4
$dens = @(
    @{ d = "mdpi";    s = 1.0 },
    @{ d = "hdpi";    s = 1.5 },
    @{ d = "xhdpi";   s = 2.0 },
    @{ d = "xxhdpi";  s = 3.0 },
    @{ d = "xxxhdpi"; s = 4.0 }
)
foreach ($x in $dens) {
    $legacy = [int](48 * $x.s)
    $fore   = [int](108 * $x.s)
    $dir    = Join-Path $res ("mipmap-" + $x.d)

    # 旧式（四角）。絵は 78% ―― 旧式は削られないので大きめに置ける
    Save-Icon (New-Icon -Size $legacy -Opaque $true  -Fill 0.78 -Round $false) (Join-Path $dir "ic_launcher.png")
    # 旧式（丸）
    Save-Icon (New-Icon -Size $legacy -Opaque $true  -Fill 0.70 -Round $true)  (Join-Path $dir "ic_launcher_round.png")
    # アダプティブの前景。**64% に収める**（外側は端末の形で削られる）
    Save-Icon (New-Icon -Size $fore   -Opaque $false -Fill 0.64 -Round $false) (Join-Path $dir "ic_launcher_foreground.png")
}

# ---- Play ストア用 512×512（透過不可）----
Save-Icon (New-Icon -Size 512 -Opaque $true -Fill 0.72 -Round $false) (Join-Path $play "play_icon_512.png")

$bmp.Dispose()
Write-Host "作った: 端末用 5密度 x 3種 ＋ Play用 512"
