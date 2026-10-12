# Monta a pasta portátil do Tolaris para Windows (64 bits).
# Requisitos na máquina de montagem: Python 3.12, Node 22 e MSYS2 com mingw-w64-ucrt-x86_64-pango.
#   ./portatil/montar-windows.ps1 -Saida dist/Tolaris -Msys C:/msys64
param(
    [string]$Saida = "dist/Tolaris",
    [string]$Msys = "C:/msys64"
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$ProgressPreference = "SilentlyContinue"

$raiz = (Resolve-Path "$PSScriptRoot/..").Path
if (Test-Path $Saida) { Remove-Item -Recurse -Force $Saida }
$app = Join-Path $Saida "app"
New-Item -ItemType Directory -Force $app | Out-Null
$temp = [IO.Path]::GetTempPath()

Write-Host "1/6 Python embutido"
$versao = (python -c "import platform; print(platform.python_version())").Trim()
$zip = Join-Path $temp "python-embed.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$versao/python-$versao-embed-amd64.zip" -OutFile $zip
Expand-Archive $zip (Join-Path $app "python")
$pth = Get-ChildItem (Join-Path $app "python/python*._pth") | Select-Object -First 1
$linhas = (Get-Content $pth) -replace '^#\s*import site', 'import site'
Set-Content $pth (@($linhas) + "Lib\site-packages")
python -m pip install --disable-pip-version-check --no-warn-script-location `
    --target (Join-Path $app "python/Lib/site-packages") "$raiz[api]"

Write-Host "2/6 Node.js"
New-Item -ItemType Directory -Force (Join-Path $app "node") | Out-Null
Copy-Item (Get-Command node).Source (Join-Path $app "node/node.exe")

Write-Host "3/6 Site (Next.js standalone)"
Push-Location (Join-Path $raiz "web")
$env:TOLARIS_API_URL = "http://127.0.0.1:8000"
$env:NEXT_TELEMETRY_DISABLED = "1"
npm ci --no-audit --no-fund
npm run build
Pop-Location
Copy-Item -Recurse -Force (Join-Path $raiz "web/.next/standalone") (Join-Path $app "web")
Copy-Item -Recurse -Force (Join-Path $raiz "web/.next/static") (Join-Path $app "web/.next/static")
Copy-Item -Recurse -Force (Join-Path $raiz "web/public") (Join-Path $app "web/public")

Write-Host "4/6 Migrações do banco"
New-Item -ItemType Directory -Force (Join-Path $app "api") | Out-Null
Copy-Item (Join-Path $raiz "alembic.ini") (Join-Path $app "api")
Copy-Item -Recurse (Join-Path $raiz "migrations") (Join-Path $app "api/migrations")

Write-Host "5/6 Bibliotecas do PDF (Pango) e fontconfig"
# O prefixo ucrt64 tem só o Pango e suas dependências: copia todas as DLLs
New-Item -ItemType Directory -Force (Join-Path $app "gtk/bin"), (Join-Path $app "gtk/etc") | Out-Null
Copy-Item (Join-Path $Msys "ucrt64/bin/*.dll") (Join-Path $app "gtk/bin")
Copy-Item -Recurse (Join-Path $Msys "ucrt64/etc/fonts") (Join-Path $app "gtk/etc/fonts")

Write-Host "6/6 Inicializador e instruções"
Copy-Item (Join-Path $raiz "portatil/iniciar.py") $app
foreach ($f in "Iniciar Tolaris.bat", "LEIA-ME.txt", "configuracao.txt") {
    Copy-Item (Join-Path $raiz "portatil/$f") $Saida
}
Get-ChildItem -Recurse -Directory -Filter __pycache__ (Join-Path $app "api") | Remove-Item -Recurse -Force

$tamanho = (Get-ChildItem -Recurse -File $Saida | Measure-Object -Sum Length).Sum / 1MB
Write-Host ("Pasta portátil pronta em {0} ({1:N0} MB)" -f $Saida, $tamanho)
