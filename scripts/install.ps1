#Requires -Version 5.1
# Install tlm from Git (PyPI not published yet). Example:
#   $env:TLM_GITHUB_REPO = "OWNER/tlm"
#   .\scripts\install.ps1 -Version 0.2.0b2
param(
    [string]$Version = "0.2.0b2"
)
$Repo = $env:TLM_GITHUB_REPO
if (-not $Repo) {
    Write-Error "Set env TLM_GITHUB_REPO to your GitHub owner/repo (e.g. myorg/tlm), then re-run."
    exit 1
}
$GitRef = if ($env:TLM_GIT_REF) { $env:TLM_GIT_REF } else { "v$Version" }
$url = "git+https://github.com/$Repo.git@$GitRef"
py -3 -m pip install --user $url
Write-Host "Installed tlm from $url (user site). Ensure Python Scripts is on PATH."
