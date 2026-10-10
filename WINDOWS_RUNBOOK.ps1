# From the repository root. Requires Python 3.11+, with internet for package installation.
$ErrorActionPreference = 'Stop'
if (Get-Command py -ErrorAction SilentlyContinue) {
  py -3.11 -m venv .venv
} else {
  python -m venv .venv
}
$python = Join-Path $PWD '.venv\Scripts\python.exe'
& $python -m pip install -e '.[dev]'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& $python -m econpipe.cli demo --db-url sqlite:///data/demo_warehouse.sqlite
& $python -m econpipe.cli demo --db-url sqlite:///data/demo_warehouse.sqlite
if ($LASTEXITCODE -ne 0) { throw 'Offline demonstration failed' }
Write-Host 'Offline pipeline verified. For actual public data, run:' -ForegroundColor Green
Write-Host '.\.venv\Scripts\python.exe -m econpipe.cli run --db-url sqlite:///data/economic_warehouse.sqlite'
Write-Host 'Inspect results/last_run.json for row counts and run twice to test idempotence.'
