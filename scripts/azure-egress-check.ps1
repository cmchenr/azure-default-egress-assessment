# Azure Default Egress Assessment Tool - PowerShell Launcher Script
# Copyright © 2025 Aviatrix Systems, Inc. All rights reserved.
#
# This script checks for Python, installs required packages, and runs the Azure Egress Assessment tool.

# Script variables
# GitHub repository information
$githubRepo = "cmchenr/azure-default-egress-assessment"
$githubBranch = "main"
# URLs for script download
$scriptUrl = "https://raw.githubusercontent.com/$githubRepo/$githubBranch/scripts/azure_egress_assessment.py"
$templateUrl = "https://raw.githubusercontent.com/$githubRepo/$githubBranch/scripts/templates/report_template.html"
# Create temporary directory and file paths for downloaded files
$tempDir = New-TemporaryFile | ForEach-Object { Remove-Item $_; New-Item -ItemType Directory -Path $_ }
$scriptPath = Join-Path $tempDir "azure_egress_assessment.py"
$templatePath = Join-Path $tempDir "report_template.html"
$venvPath = Join-Path $tempDir "venv"
$requirements = @(
    "azure-identity",
    "azure-mgmt-resource",
    "azure-mgmt-network",
    "azure-mgmt-subscription",
    "Jinja2"
)

# Print banner
Write-Host "======================================================" -ForegroundColor Blue
Write-Host "    Azure Default Egress Assessment Tool - Launcher   " -ForegroundColor Blue
Write-Host "======================================================" -ForegroundColor Blue
Write-Host ""
Write-Host "Copyright © 2025 Aviatrix Systems, Inc. All rights reserved." -ForegroundColor Cyan
Write-Host ""

# Function to check if a command exists
function Test-CommandExists {
    param (
        [string]$command
    )
    
    $exists = $null -ne (Get-Command $command -ErrorAction SilentlyContinue)
    return $exists
}

# Function to get Python executable
function Get-PythonExecutable {
    if (Test-CommandExists "python") {
        $pythonVersion = & python --version 2>&1
        if ($pythonVersion -match "Python 3") {
            return "python"
        }
    }
    
    if (Test-CommandExists "python3") {
        return "python3"
    }
    
    if (Test-CommandExists "py") {
        return "py -3"
    }
    
    return $null
}

# Function to check Python version
function Test-PythonVersion {
    param (
        [string]$pythonExe
    )
    
    try {
        $pythonVersionOutput = Invoke-Expression "$pythonExe --version 2>&1"
        if ($pythonVersionOutput -match "Python (\d+)\.(\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            
            if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 6)) {
                return $false
            } else {
                return $true
            }
        }
        return $false
    } catch {
        return $false
    }
}

# Function to create virtual environment and install packages
function Setup-VirtualEnvironment {
    param (
        [string]$pythonExe
    )
    
    Write-Host "`nCreating virtual environment for package isolation..." -ForegroundColor Blue
    Write-Host "This avoids conflicts with system Python packages." -ForegroundColor Blue
    
    try {
        # Create virtual environment
        Write-Host "Creating virtual environment at: $venvPath" -ForegroundColor Blue
        & $pythonExe -m venv $venvPath
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment"
        }
        
        Write-Host "✓ Virtual environment created successfully" -ForegroundColor Green
        
        # Get the virtual environment Python executable
        $venvPython = if ($IsWindows -or $env:OS -eq "Windows_NT") {
            Join-Path $venvPath "Scripts\python.exe"
        } else {
            Join-Path $venvPath "bin/python"
        }
        
        # Verify the virtual environment Python exists
        if (-not (Test-Path $venvPython)) {
            throw "Virtual environment Python not found at $venvPython"
        }
        
        $pythonVersion = & $venvPython --version
        Write-Host "Using virtual environment Python: $pythonVersion" -ForegroundColor Blue
        
        # Update pip in virtual environment
        Write-Host "Updating pip in virtual environment..." -ForegroundColor Blue
        & $venvPython -m pip install --upgrade pip --quiet
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to upgrade pip in virtual environment"
        }
        
        # Install each required package in virtual environment
        Write-Host "Installing required packages in virtual environment..." -ForegroundColor Blue
        foreach ($package in $requirements) {
            Write-Host "Installing $package..." -ForegroundColor Blue
            & $venvPython -m pip install --upgrade $package --quiet
            
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install $package in virtual environment"
            }
        }
        
        Write-Host "✓ All required packages installed successfully in virtual environment" -ForegroundColor Green
        
        # Return the virtual environment python path
        return $venvPython
        
    } catch {
        Write-Host "Error setting up virtual environment: $_" -ForegroundColor Red
        
        # Provide platform-specific guidance
        if ($IsWindows -or $env:OS -eq "Windows_NT") {
            Write-Host "On Windows, venv should be included with Python 3.3+" -ForegroundColor Yellow
            Write-Host "If you continue to have issues, try:" -ForegroundColor Yellow
            Write-Host "  1. Reinstall Python from python.org with 'Add to PATH' option" -ForegroundColor Yellow
            Write-Host "  2. Or install via Windows Store: ms-windows-store://pdp/?productid=9NRWMJP3717K" -ForegroundColor Yellow
        } else {
            Write-Host "On this platform, ensure Python venv module is available" -ForegroundColor Yellow
            Write-Host "Try installing via your package manager or from python.org" -ForegroundColor Yellow
        }
        
        throw "Cannot create virtual environment"
    }
}

# Function to download the assessment script and template
function Download-Script {
    Write-Host "`nDownloading the Azure Egress Assessment script and template from GitHub..." -ForegroundColor Blue
    
    try {
        # Download the main script from GitHub
        Invoke-WebRequest -Uri $scriptUrl -OutFile $scriptPath -UseBasicParsing
        Write-Host "Assessment script downloaded successfully from GitHub." -ForegroundColor Green
        
        # Download the report template from GitHub
        Invoke-WebRequest -Uri $templateUrl -OutFile $templatePath -UseBasicParsing
        Write-Host "Report template downloaded successfully from GitHub." -ForegroundColor Green
        
    } catch {
        Write-Host "Error downloading files from GitHub: $_" -ForegroundColor Red
        Write-Host "Script URL: $scriptUrl" -ForegroundColor Red
        Write-Host "Template URL: $templateUrl" -ForegroundColor Red
        throw "Failed to download required files"
    }
}

# Function to check if Azure CLI is logged in
function Check-AzureLogin {
    Write-Host "`nChecking Azure CLI login status..." -ForegroundColor Blue
    
    if (Test-CommandExists "az") {
        try {
            $null = & az account show 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Azure CLI is logged in." -ForegroundColor Green
            } else {
                Write-Host "You are not logged into Azure CLI. Please log in:" -ForegroundColor Yellow
                & az login
                
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "Azure login failed. Please make sure Azure CLI is properly installed and try again." -ForegroundColor Red
                    throw "Azure CLI login failed"
                }
                
                Write-Host "Azure CLI login successful." -ForegroundColor Green
            }
        } catch {
            Write-Host "Error checking Azure CLI status: $_" -ForegroundColor Yellow
            Write-Host "The script will try to use DefaultAzureCredential instead." -ForegroundColor Yellow
        }
    } else {
        Write-Host "Azure CLI not found. The script will try to use DefaultAzureCredential instead." -ForegroundColor Yellow
        Write-Host "If authentication fails, please install Azure CLI from:" -ForegroundColor Yellow
        Write-Host "    https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Yellow
    }
}

# Function to run the assessment
function Run-Assessment {
    param (
        [string]$venvPythonExe,
        [string[]]$ScriptArgs
    )
    
    Write-Host "`nRunning Azure Default Egress Assessment..." -ForegroundColor Blue
    Write-Host "This may take several minutes depending on the size of your Azure environment.`n" -ForegroundColor Blue
    
    # Execute the downloaded script using virtual environment Python
    & $venvPythonExe $scriptPath @ScriptArgs
}

# Function to install Python if it's not found
function Install-Python {
    Write-Host "Python 3.6+ is required but not found." -ForegroundColor Red
    
    # Provide installation guidance based on platform
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        Write-Host "On Windows, you can install Python using:" -ForegroundColor Yellow
        Write-Host "Option 1 - Microsoft Store (Recommended):" -ForegroundColor Blue
        Write-Host "  Search for 'Python' in Microsoft Store and install Python 3.x" -ForegroundColor Yellow
        Write-Host "Option 2 - Official Python.org installer:" -ForegroundColor Blue
        Write-Host "  Download from https://www.python.org/downloads/windows/" -ForegroundColor Yellow
        Write-Host "Option 3 - Windows Package Manager (if available):" -ForegroundColor Blue
        Write-Host "  winget install Python.Python.3" -ForegroundColor Yellow
        
        # Try winget first if available
        if (Test-CommandExists "winget") {
            Write-Host "`nAttempting to install Python via winget..." -ForegroundColor Blue
            try {
                & winget install Python.Python.3 --silent --accept-package-agreements --accept-source-agreements
                
                # Refresh PATH
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
                
                Start-Sleep -Seconds 3  # Give time for installation to complete
                
                $pythonExe = Get-PythonExecutable
                if ($pythonExe) {
                    Write-Host "Python installed successfully via winget." -ForegroundColor Green
                    return $pythonExe
                }
            } catch {
                Write-Host "winget installation failed: $_" -ForegroundColor Yellow
            }
        }
        
        # Try Chocolatey if available
        if (Test-CommandExists "choco") {
            Write-Host "`nAttempting to install Python via Chocolatey..." -ForegroundColor Blue
            try {
                & choco install python -y
                
                # Refresh PATH
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
                
                $pythonExe = Get-PythonExecutable
                if ($pythonExe) {
                    Write-Host "Python installed successfully via Chocolatey." -ForegroundColor Green
                    return $pythonExe
                }
            } catch {
                Write-Host "Chocolatey installation failed: $_" -ForegroundColor Yellow
            }
        }
        
    } else {
        Write-Host "On this platform, please install Python 3.6+ using your package manager:" -ForegroundColor Yellow
        Write-Host "  macOS (Homebrew): brew install python" -ForegroundColor Yellow
        Write-Host "  Ubuntu/Debian:    sudo apt-get install python3 python3-venv" -ForegroundColor Yellow
        Write-Host "  RHEL/CentOS:      sudo yum install python3 python3-venv" -ForegroundColor Yellow
        Write-Host "  Or download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    }
    
    Write-Host "`nAfter installing Python, please restart this script." -ForegroundColor Red
    return $null
}

# Main script execution
function Main {
    param (
        [Parameter(ValueFromRemainingArguments=$true)]
        [string[]]$ScriptArgs
    )
    
    try {
        # Check for Python 3.6+
        $pythonExe = Get-PythonExecutable
        
        if (-not $pythonExe) {
            $pythonExe = Install-Python
            
            if (-not $pythonExe) {
                throw "Python installation failed"
            }
        }
        
        # Check Python version
        if (-not (Test-PythonVersion $pythonExe)) {
            $currentVersion = & $pythonExe --version 2>&1
            Write-Host "Error: Python 3.6+ is required." -ForegroundColor Red
            Write-Host "Current version: $currentVersion" -ForegroundColor Yellow
            throw "Python version requirement not met"
        } else {
            $currentVersion = & $pythonExe --version
            Write-Host "Found $currentVersion" -ForegroundColor Green
        }
        
        # Always download the latest script and template from GitHub
        Download-Script
        
        # Setup virtual environment and install required packages
        $venvPython = Setup-VirtualEnvironment $pythonExe
        
        # Check Azure login status
        Check-AzureLogin
        
        # Run the assessment using virtual environment Python
        Run-Assessment $venvPython $ScriptArgs
        
    } catch {
        Write-Host "Error: $_" -ForegroundColor Red
        exit 1
    } finally {
        # Clean up the temporary directory
        if (Test-Path $tempDir) {
            Write-Host "`nCleaning up temporary files..." -ForegroundColor Blue
            Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# Execute main with all args
Main $args
