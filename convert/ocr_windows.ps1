# Windows' own OCR (Windows.Media.Ocr, Arabic), one page image at a time.
# For each image.png writes image.words.json: every word read, with its box
# in the image's pixels. Used by convert/witness.py as a second reading of
# the page that does not share the PDF's hidden text (FLAGS 25).
#
#   powershell -File ocr_windows.ps1 page1.png page2.png ...
$Images = $args
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$t) {
    $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(); $task.Result
}
$lang = New-Object Windows.Globalization.Language 'ar-SA'
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) { Write-Error 'no Arabic OCR on this machine'; exit 2 }
foreach ($img in $Images) {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Resolve-Path $img).Path)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bmp = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
    $out = [IO.Path]::ChangeExtension($img, '.words.json')
    $rows = foreach ($line in $res.Lines) { foreach ($w in $line.Words) {
        $r = $w.BoundingRect
        [pscustomobject]@{ t = $w.Text; x = $r.X; y = $r.Y; w = $r.Width; h = $r.Height } } }
    [IO.File]::WriteAllText($out, (ConvertTo-Json @($rows) -Depth 3), [Text.Encoding]::UTF8)
    $stream.Dispose()
}
