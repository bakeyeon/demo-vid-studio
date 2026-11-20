# Installs demo-vid-studio globally for Antigravity, Claude Code, and Gemini CLI on Windows.
# Usage: .\install.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillSource = Join-Path $RepoRoot "skills\demo-vid-studio"

$Targets = @(
    @{ Name = "Antigravity"; Path = Join-Path $HOME ".gemini\config\skills\demo-vid-studio" },
    @{ Name = "Claude Code"; Path = Join-Path $HOME ".claude\skills\demo-vid-studio" },
    @{ Name = "Gemini CLI";  Path = Join-Path $HOME ".gemini\skills\demo-vid-studio" }
)

foreach ($t in $Targets) {
    $parent = Split-Path -Parent $t.Path
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    if (Test-Path $t.Path) {
        Remove-Item -Recurse -Force $t.Path
    }
    Copy-Item -Recurse -Force $SkillSource $t.Path
    Write-Host "[OK] Installed demo-vid-studio for $($t.Name) -> $($t.Path)" -ForegroundColor Green
}

Write-Host "`nAll set! Ask Antigravity or Claude Code: 'Record a demo video for this project'" -ForegroundColor Cyan
