# ロボ・スピード 実機テスト用の簡易サーバー
#
#   powershell -ExecutionPolicy Bypass -File serve.ps1
#
# 同じ Wi-Fi につないだスマホから、表示された URL を開いてください。
# HttpListener ではなく TcpListener を使っています（管理者権限が要らないため）。

$port = 8080
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'docs'))

$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $port)
try {
    $listener.Start()
} catch {
    Write-Host "ポート $port を開けませんでした。別のアプリが使っている可能性があります。" -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}

$ips = Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
       Select-Object -ExpandProperty IPAddress

Write-Host ""
Write-Host "  配信中: $root" -ForegroundColor Cyan
Write-Host ""
Write-Host "  この PC   http://localhost:$port/playtest.html" -ForegroundColor Green
foreach ($ip in $ips) {
    Write-Host "  スマホ    http://${ip}:$port/playtest.html" -ForegroundColor Green
}
Write-Host ""
Write-Host "  止めるときは Ctrl+C" -ForegroundColor DarkGray
Write-Host ""

$mime = @{
    '.html' = 'text/html; charset=utf-8'
    '.png'  = 'image/png'
    '.jpg'  = 'image/jpeg'
    '.css'  = 'text/css; charset=utf-8'
    '.js'   = 'application/javascript; charset=utf-8'
    '.md'   = 'text/plain; charset=utf-8'
    '.webp' = 'image/webp'
    '.glb'  = 'model/gltf-binary'
    '.wav'  = 'audio/wav'
    '.mp3'  = 'audio/mpeg'
    '.ogg'  = 'audio/ogg'
    '.mp4'  = 'video/mp4'
}

try {
    while ($true) {
        # 接続の受け付けで一度でも失敗したら、以前はループごと終了して
        # サーバーが黙って落ちていた。1件の失敗で止めない。
        try {
            $client = $listener.AcceptTcpClient()
        } catch {
            Write-Host "接続の受け付けに失敗しました。継続します: $($_.Exception.Message)" -ForegroundColor DarkYellow
            continue
        }
        try {
            $stream = $client.GetStream()
            $stream.ReadTimeout = 5000

            # リクエスト行だけ読めれば足りる
            $buf = New-Object byte[] 4096
            $n = $stream.Read($buf, 0, $buf.Length)
            if ($n -le 0) { $client.Close(); continue }
            $head = [System.Text.Encoding]::ASCII.GetString($buf, 0, $n)
            $first = ($head -split "`r`n")[0]
            $target = ($first -split ' ')[1]
            if (-not $target) { $target = '/' }
            $target = ($target -split '\?')[0]

            $rel = [System.Uri]::UnescapeDataString($target).TrimStart('/')
            if ([string]::IsNullOrEmpty($rel)) { $rel = 'playtest.html' }
            $rel = $rel -replace '/', '\'

            $full = [System.IO.Path]::GetFullPath((Join-Path $root $rel))

            # docs/ の外へは出させない
            if ($full.StartsWith($root) -and (Test-Path $full -PathType Leaf)) {
                $ext = [System.IO.Path]::GetExtension($full).ToLower()
                $type = if ($mime.ContainsKey($ext)) { $mime[$ext] } else { 'application/octet-stream' }
                $body = [System.IO.File]::ReadAllBytes($full)
                $status = '200 OK'
            } else {
                $type = 'text/plain; charset=utf-8'
                $body = [System.Text.Encoding]::UTF8.GetBytes("404 $rel")
                $status = '404 Not Found'
            }

            $header = "HTTP/1.1 $status`r`n" +
                      "Content-Type: $type`r`n" +
                      "Content-Length: $($body.Length)`r`n" +
                      "Cache-Control: no-store`r`n" +
                      "Connection: close`r`n`r`n"
            $hb = [System.Text.Encoding]::ASCII.GetBytes($header)
            $stream.Write($hb, 0, $hb.Length)
            $stream.Write($body, 0, $body.Length)
            $stream.Flush()
        } catch {
            # 1リクエストの失敗でサーバーを止めない
        } finally {
            $client.Close()
        }
    }
} finally {
    $listener.Stop()
}
