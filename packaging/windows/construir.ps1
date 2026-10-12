# Construye el instalador de Bildumargi para Windows.
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows\construir.ps1
#
# Hace falta, una sola vez:
#   python -m pip install -r requirements.txt -r packaging\windows\requisitos.txt
#   Inno Setup 6 (https://jrsoftware.org/isdl.php)
#
# Deja el instalador en build\windows\Bildumargi-<versión>-instalador.exe.

$ErrorActionPreference = "Stop"
$raiz = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $raiz

Write-Host "== 1/3 Icono"
python packaging\windows\crear_icono.py

Write-Host "== 2/3 Aplicación (PyInstaller)"
python -m PyInstaller packaging\windows\bildumargi.spec --noconfirm --log-level WARN `
    --distpath build\windows\dist --workpath build\windows\trabajo
if (-not (Test-Path build\windows\dist\Bildumargi\Bildumargi.exe)) { throw "PyInstaller no ha creado Bildumargi.exe" }

Write-Host "== 3/3 Instalador (Inno Setup)"
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "No se encuentra Inno Setup 6 (ISCC.exe). Instálalo desde https://jrsoftware.org/isdl.php" }
& $iscc /Q packaging\windows\bildumargi.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup ha fallado" }

$instalador = Get-ChildItem build\windows\Bildumargi-*-instalador.exe | Sort-Object LastWriteTime | Select-Object -Last 1
$huella = (Get-FileHash $instalador.FullName -Algorithm SHA256).Hash.ToLower()
"$huella  $($instalador.Name)" | Set-Content "$($instalador.FullName).sha256" -Encoding ascii
Write-Host ("Listo: {0} ({1:N0} MB)" -f $instalador.FullName, ($instalador.Length / 1MB))
Write-Host "SHA-256: $huella"
