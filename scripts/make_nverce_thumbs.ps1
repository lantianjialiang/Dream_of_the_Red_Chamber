$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Drawing
# 采集底本已移出仓库，归档在 _archive/retired/nverce-source/（不入库）
$root = Join-Path (Split-Path -Parent $PSScriptRoot) '_archive\retired\nverce-source'
$src = Join-Path $root 'images'
$dst = Join-Path $root 'thumbs'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
$codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
$params = New-Object System.Drawing.Imaging.EncoderParameters 1
$params.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality, [long]80)
$n = 0
Get-ChildItem -Path $src -File | ForEach-Object {
  $out = Join-Path $dst ($_.BaseName + '.jpg')
  if (Test-Path $out) { return }
  try {
    $bmp = [System.Drawing.Bitmap]::FromFile($_.FullName)
    $max = 560.0
    $r = [math]::Min($max / $bmp.Width, $max / $bmp.Height)
    if ($r -gt 1) { $r = 1 }
    $nw = [int]($bmp.Width * $r); $nh = [int]($bmp.Height * $r)
    $thumb = New-Object System.Drawing.Bitmap $nw, $nh
    $g = [System.Drawing.Graphics]::FromImage($thumb)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.DrawImage($bmp, 0, 0, $nw, $nh)
    $g.Dispose(); $bmp.Dispose()
    $thumb.Save($out, $codec, $params)
    $thumb.Dispose()
    $n++
  } catch { }
}
$params.Dispose()
Write-Output ("THUMBS " + $n)
