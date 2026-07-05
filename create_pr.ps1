param(
    [string]$Branch,
    [string]$Title,
    [string]$CommitMessage,
    [string]$BaseBranch = "main"
)

$ErrorActionPreference = "Stop"

$RepositoryUrl = "https://github.com/KefirZephyr/catboom_analyst.git"
$RepositoryFullName = "KefirZephyr/catboom_analyst"
$SafetyPatterns = @(
    ".env",
    "*.session",
    "*.session-journal",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "__pycache__/",
    ".pytest_cache/",
    ".venv/",
    "venv/",
    "logs/",
    "*.log"
)
$DangerousTrackedPattern = '(^|/)\.env$|\.session$|\.session-journal$|\.db$|\.sqlite$|\.sqlite3$|(^|/)\.venv/|(^|/)venv/|(^|/)__pycache__/|(^|/)\.pytest_cache/|(^|/)logs/|\.log$'

function Fail($Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

function Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Run($Command, [string[]]$Arguments) {
    Write-Host "+ $Command $($Arguments -join ' ')" -ForegroundColor DarkGray
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail "Command failed: $Command $($Arguments -join ' ')"
    }
}

function Require-Command($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Fail "$Name is not installed or not available in PATH."
    }
}

function Get-GitOutput([string[]]$Arguments) {
    $output = & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail "Git command failed: git $($Arguments -join ' ')"
    }
    return $output
}

function Test-DangerousPath($Path) {
    $normalized = $Path -replace '\\', '/'
    return $normalized -match $DangerousTrackedPattern
}

function Ensure-Gitignore {
    Step "Checking .gitignore"
    if (-not (Test-Path ".gitignore")) {
        New-Item -Path ".gitignore" -ItemType File | Out-Null
    }

    $content = @(Get-Content ".gitignore" -ErrorAction SilentlyContinue)
    $missing = @()
    foreach ($pattern in $SafetyPatterns) {
        if ($pattern -notin $content) {
            $missing += $pattern
        }
    }

    if ($missing.Count -gt 0) {
        Add-Content -Path ".gitignore" -Value ""
        Add-Content -Path ".gitignore" -Value "# Local secrets, databases, caches, and logs"
        foreach ($pattern in $missing) {
            Add-Content -Path ".gitignore" -Value $pattern
        }
        Write-Host "Added missing .gitignore rules: $($missing -join ', ')"
    } else {
        Write-Host ".gitignore safety rules are present."
    }
}

function Assert-NoDangerousTrackedFiles {
    Step "Checking tracked files for local secrets and runtime data"
    $tracked = @(Get-GitOutput @("ls-files") | Where-Object { Test-DangerousPath $_ })
    if ($tracked.Count -gt 0) {
        $tracked | ForEach-Object { Write-Host "Blocked tracked file: $_" -ForegroundColor Red }
        Fail "Dangerous files are tracked by git. Remove them from the index with git rm --cached before continuing."
    }
    Write-Host "Safety passed: no dangerous tracked files."
}

function Assert-NoDangerousStagedFiles {
    Step "Checking staged files"
    $staged = @(Get-GitOutput @("diff", "--cached", "--name-only") | Where-Object { Test-DangerousPath $_ })
    if ($staged.Count -gt 0) {
        $staged | ForEach-Object { Write-Host "Blocked staged file: $_" -ForegroundColor Red }
        Fail "Dangerous files are staged. Commit was stopped."
    }
    Write-Host "Safety passed: no dangerous staged files."
}

function Assert-EnvExampleIsSafe {
    Step "Checking .env.example"
    if (-not (Test-Path ".env.example")) {
        Fail ".env.example not found."
    }

    $text = Get-Content ".env.example" -Raw
    $problems = @()
    if ($text -match 'BOT_TOKEN=\d+:[A-Za-z0-9_-]{20,}') {
        $problems += "BOT_TOKEN looks real"
    }
    if ($text -match 'API_HASH=(?!YOUR_|$)[a-fA-F0-9]{32}') {
        $problems += "API_HASH looks real"
    }
    if ($text -match 'PANDASCORE_TOKEN=(?!YOUR_|$)[A-Za-z0-9_-]{20,}') {
        $problems += "PANDASCORE_TOKEN looks real"
    }

    if ($problems.Count -gt 0) {
        $problems | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        Fail ".env.example may contain real secrets."
    }
    Write-Host ".env.example contains placeholders only."
}

function Get-AutoTitle([string[]]$Files) {
    if ($Files.Count -eq 0) {
        return "Update project"
    }
    if ($Files -contains "create_pr.ps1") {
        return "Add automated PR helper"
    }
    if ($Files | Where-Object { $_ -like "*.md" }) {
        return "Update documentation"
    }
    if ($Files | Where-Object { $_ -like "tests/*" }) {
        return "Update tests"
    }
    return "Update CatBoom Dota Analyst v2"
}

function New-PrBody([string]$PrTitle, [string]$BranchName, [string[]]$Files) {
    $fileLines = if ($Files.Count -gt 0) {
        ($Files | ForEach-Object { "- $_" }) -join [Environment]::NewLine
    } else {
        "- No changed files detected"
    }

    return @"
## Summary
- $PrTitle
- Created from branch `$BranchName`
- No auto-betting, bookmaker integration, or force push is used by this helper.

## Changed files
$fileLines

## Validation
- python -m compileall .
- python -c "from config.settings import settings; print('settings ok')"
- pytest

## Safety
- .env, session files, databases, virtual environments, caches, and logs are blocked from git.
- .env.example is checked for real-looking secrets.
"@
}

Set-Location $PSScriptRoot

Step "Checking required tools"
Require-Command "git"
Require-Command "gh"
Require-Command "python"
Run "gh" @("auth", "status")

Step "Checking git repository"
Run "git" @("rev-parse", "--is-inside-work-tree")

$stashedChanges = $false
$initialStatus = @(Get-GitOutput @("status", "--porcelain"))
if ($initialStatus.Count -gt 0) {
    Step "Saving current working tree before syncing $BaseBranch"
    Run "git" @("stash", "push", "-u", "-m", "catboom-create-pr-auto-stash")
    $stashedChanges = $true
}

Step "Checking origin"
$origin = & git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    Run "git" @("remote", "add", "origin", $RepositoryUrl)
} elseif ($origin -ne $RepositoryUrl) {
    Run "git" @("remote", "set-url", "origin", $RepositoryUrl)
}

Step "Syncing $BaseBranch"
Run "git" @("fetch", "origin")
Run "git" @("checkout", $BaseBranch)
Run "git" @("pull", "origin", $BaseBranch)

if (-not $Branch) {
    $Branch = "chore/auto-pr-$(Get-Date -Format 'yyyyMMdd-HHmm')"
}

Step "Preparing branch $Branch"
$localBranch = & git branch --list $Branch
if ($localBranch) {
    Run "git" @("checkout", $Branch)
} else {
    Run "git" @("checkout", "-b", $Branch)
}

if ($stashedChanges) {
    Step "Restoring saved working tree"
    Run "git" @("stash", "pop")
}

Ensure-Gitignore
Assert-NoDangerousTrackedFiles
Assert-EnvExampleIsSafe

Step "Running checks"
Run "python" @("-m", "compileall", ".")
Run "python" @("-c", "from config.settings import settings; print('settings ok')")
Run "pytest" @()

Step "Staging safe files"
Run "git" @("add", ".")
Assert-NoDangerousStagedFiles

$changedFiles = @(Get-GitOutput @("diff", "--cached", "--name-only"))
if ($changedFiles.Count -eq 0) {
    Write-Host "No changes to commit."
} else {
    if (-not $Title) {
        $Title = Get-AutoTitle $changedFiles
    }
    if (-not $CommitMessage) {
        $CommitMessage = $Title
    }

    Step "Creating commit"
    Run "git" @("commit", "-m", $CommitMessage)
}

$commitHash = (Get-GitOutput @("rev-parse", "HEAD")).Trim()
if (-not $Title) {
    $Title = (Get-GitOutput @("log", "-1", "--pretty=%s")).Trim()
}

Step "Pushing branch"
Run "git" @("push", "-u", "origin", $Branch)

$body = New-PrBody $Title $Branch $changedFiles
$existingPrUrl = (& gh pr view --head $Branch --base $BaseBranch --json url --jq ".url" 2>$null)

Step "Creating or updating pull request"
if ($LASTEXITCODE -eq 0 -and $existingPrUrl) {
    Run "gh" @("pr", "edit", $existingPrUrl, "--title", $Title, "--body", $body)
    $prUrl = $existingPrUrl
    Write-Host "Updated existing PR: $prUrl"
} else {
    $prUrl = (& gh pr create --base $BaseBranch --head $Branch --title $Title --body $body)
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to create pull request."
    }
    Write-Host "Created PR: $prUrl"
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "branch: $Branch"
Write-Host "commit hash: $commitHash"
Write-Host "PR URL: $prUrl"
Write-Host "checks passed: compileall, settings import, pytest"
Write-Host "safety passed: gitignore, tracked files, staged files, .env.example"
