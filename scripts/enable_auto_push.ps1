param(
    [string]$Remote = "origin"
)

$ErrorActionPreference = "Stop"
$repoRoot = git rev-parse --show-toplevel
if (-not $repoRoot) { throw "Run this script inside a Git repository." }

$hooksDir = Join-Path $repoRoot ".git\hooks"
$hookPath = Join-Path $hooksDir "post-commit"
$hook = @"
#!/bin/sh
branch=`$(git branch --show-current)
if [ -n "`$branch" ]; then
  git push -u $Remote "`$branch"
fi
"@

Set-Content -LiteralPath $hookPath -Value $hook -Encoding ascii
Write-Host "Enabled automatic push to '$Remote' after every commit."
