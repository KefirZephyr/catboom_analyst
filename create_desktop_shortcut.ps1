$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$targetPath = Join-Path $projectDir "run_bot.bat"

if (-not (Test-Path $targetPath)) {
    throw "run_bot.bat was not found in project directory: $projectDir"
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "CatBoom Dota Analyst v2.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $projectDir
$shortcut.Description = "Start CatBoom Dota Analyst v2"
$shortcut.Save()

Write-Host "Shortcut created: $shortcutPath"
