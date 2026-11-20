[CmdletBinding()]
param(
    [ValidateSet('setup', 'doctor', 'test', 'gl-test', 'synth', 'wave', 'viewer', 'help')]
    [string]$Command = 'help',
    [string]$Archive = (Join-Path $env:USERPROFILE 'Downloads\oss-cad-suite-windows-x64-20261120.tgz'),
    [string]$Waveform = 'test\tb.fst'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $projectRoot '.tools'
$suiteDir = Join-Path $toolsDir 'oss-cad-suite'
if ($env:OSS_CAD_SUITE) { $suiteDir = [IO.Path]::GetFullPath($env:OSS_CAD_SUITE) }
$pythonDir = Join-Path $toolsDir 'python'
$pythonExe = Join-Path $pythonDir 'python.exe'

function Assert-Exit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) { throw "$Operation failed (exit $LASTEXITCODE)." }
}

function Enable-Suite {
    $environmentScript = Join-Path $suiteDir 'environment.ps1'
    if (-not (Test-Path -LiteralPath $environmentScript)) {
        throw 'OSS CAD Suite is missing. Run .\tt.cmd setup first.'
    }
    # Always select this project's suite, even if another suite was activated earlier.
    $env:YOSYSHQ_ROOT = $suiteDir
    . $environmentScript
}

try {
    if ($Command -eq 'help') {
        Write-Output @'
Run from the project folder:
  .\tt.cmd setup                 Extract the archive and install local test dependencies
  .\tt.cmd doctor                Check the project and tools
  .\tt.cmd test                  Run the existing exhaustive cocotb test
  .\tt.cmd synth                 Check/synthesize RTL with Yosys
  .\tt.cmd wave                  Open test/tb.fst in GTKWave
  .\tt.cmd wave -Waveform PATH   Open a downloaded RTL or gate-level waveform
  .\tt.cmd gl-test               Test an existing Sky130 netlist (requires PDK_ROOT)
  .\tt.cmd viewer                Open this repository's published 3D layout
See docs/windows-and-github.md for GitHub Actions, Pages, and local hardening.
'@
        exit 0
    }

    if ($Command -eq 'viewer') {
        Start-Process 'https://sul-tan1.github.io/tqt_tt_workshop_ex/'
        exit 0
    }

    if ($Command -eq 'setup') {
        New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
        if (-not (Test-Path -LiteralPath (Join-Path $suiteDir 'environment.ps1'))) {
            if ($env:OSS_CAD_SUITE) { throw 'OSS_CAD_SUITE must point to an already extracted suite.' }
            if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) {
                throw "Archive not found: $Archive. Use .\tt.cmd setup -Archive 'C:\path\to\archive.tgz'."
            }
            Write-Output "Extracting $Archive ..."
            $entries = & tar.exe -tzf $Archive
            Assert-Exit 'Reading archive'
            foreach ($entry in $entries) {
                if ($entry -notmatch '^oss-cad-suite(/|$)' -or $entry -match '(^|/)\.\.(/|$)|\\') {
                    throw "Unexpected archive entry: $entry"
                }
            }
            & tar.exe -xzf $Archive -C $toolsDir
            Assert-Exit 'Extracting OSS CAD Suite'
        }

        # The suite bundles a MinGW Python. Use a separate CPython for the official
        # Windows cocotb wheels; keep both runtimes entirely inside this project.
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        if (-not (Test-Path -LiteralPath $pythonExe)) {
            $pythonZip = Join-Path $toolsDir 'python-3.11.9-embed-amd64.zip'
            Write-Output 'Downloading portable CPython 3.11.9 from python.org ...'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile $pythonZip
            Expand-Archive -LiteralPath $pythonZip -DestinationPath $pythonDir -Force
        }
        # The embedded runtime uses an explicit import path, also when loaded by vvp.
        @('python311.zip', '.', 'Lib\site-packages', '..\..\test', 'import site') |
            Set-Content -LiteralPath (Join-Path $pythonDir 'python311._pth') -Encoding ASCII
        if (-not (Test-Path -LiteralPath (Join-Path $pythonDir 'Lib\site-packages\pip\__main__.py'))) {
            $pipBootstrap = Join-Path $toolsDir 'get-pip.py'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile $pipBootstrap
            & $pythonExe $pipBootstrap --disable-pip-version-check --no-warn-script-location
            Assert-Exit 'Installing pip'
        }
        & $pythonExe -m pip install --disable-pip-version-check --no-warn-script-location -r (Join-Path $PSScriptRoot 'requirements.txt')
        Assert-Exit 'Installing test dependencies'
        Enable-Suite
        & $pythonExe (Join-Path $PSScriptRoot 'run.py') doctor
        Assert-Exit 'Checking setup'
        Write-Output 'Ready. Run .\tt.cmd test, then .\tt.cmd wave.'
        exit 0
    }

    Enable-Suite
    if ($Command -eq 'wave') {
        if (-not [IO.Path]::IsPathRooted($Waveform)) { $Waveform = Join-Path $projectRoot $Waveform }
        if (-not (Test-Path -LiteralPath $Waveform -PathType Leaf)) {
            throw "Waveform missing: $Waveform. Run .\tt.cmd test first, or pass -Waveform."
        }
        # GTKWave is the interactive window requested by this command.
        Start-Process -FilePath (Join-Path $suiteDir 'bin\gtkwave.exe') -WorkingDirectory $projectRoot -ArgumentList @(
            ('"{0}"' -f $Waveform), ('"{0}"' -f (Join-Path $projectRoot 'test\tb.gtkw'))
        )
        exit 0
    }
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run .\tt.cmd setup to install the local test runtime.' }
    & $pythonExe (Join-Path $PSScriptRoot 'run.py') $Command
    Assert-Exit $Command
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
