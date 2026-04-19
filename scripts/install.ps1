#Requires -Version 5.1
# Experimental Windows installer placeholder for tlm 0.2.x.
# Prefer: py -3.11 -m pip install --user tlm==0.2.0b2
param(
    [string]$Version = "0.2.0b2",
    [switch]$Experimental
)
if (-not $Experimental) {
    Write-Error "Windows install is experimental. Run: py -3.11 -m pip install --user tlm==$Version"
    exit 1
}
py -3 -m pip install --user "tlm==$Version"
Write-Host "Installed tlm $Version (user site). Ensure Python Scripts is on PATH."
