# Azure Default Egress Assessment Tool - PowerShell Launcher Script
# Copyright © 2025 Aviatrix Systems, Inc. All rights reserved.
#
# This script checks for Python, installs required packages, and runs the Azure Egress Assessment tool.

# Script variables
# In a production environment, this would be a real URL to the hosted script
# For our test purpose, we'll use the local file
$scriptUrl = "https://example.com/azure_egress_assessment.py"
# For local testing, use the actual file path
$scriptPath = "/Users/christophermchenry/Documents/Scripting/azure-default-egress-assessment/scripts/azure_egress_assessment.py"
$requirements = @(
    "azure-identity",
    "azure-mgmt-resource",
    "azure-mgmt-network",
    "azure-mgmt-subscription"
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

# Function to install packages using pip
function Install-Packages {
    param (
        [string]$pythonExe
    )
    
    Write-Host "`nChecking and installing required Python packages..." -ForegroundColor Blue
    
    # Check if pip exists
    try {
        $pipExists = $null -ne (Invoke-Expression "$pythonExe -m pip --version" -ErrorAction SilentlyContinue)
        
        if (-not $pipExists) {
            Write-Host "pip not found. Attempting to install pip..." -ForegroundColor Yellow
            $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
            $getPipPath = Join-Path $env:TEMP "get-pip.py"
            
            Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath
            & $pythonExe $getPipPath --user
            Remove-Item $getPipPath -Force
        }
        
        # Update pip
        Write-Host "Updating pip..." -ForegroundColor Blue
        Invoke-Expression "$pythonExe -m pip install --upgrade pip --quiet"
        
        # Install each required package
        foreach ($package in $requirements) {
            Write-Host "Installing $package..." -ForegroundColor Blue
            Invoke-Expression "$pythonExe -m pip install --upgrade $package --quiet"
        }
        
        Write-Host "All required packages installed successfully." -ForegroundColor Green
        
    } catch {
        Write-Host "Error installing packages: $_" -ForegroundColor Red
        Write-Host "Please try installing the packages manually with: $pythonExe -m pip install $($requirements -join ' ')" -ForegroundColor Yellow
        exit 1
    }
}

# Function to download the assessment script
function Download-Script {
    # For local testing, check if the script already exists at the path
    if (Test-Path $scriptPath) {
        Write-Host "`nUsing existing script at $scriptPath" -ForegroundColor Green
        return
    }
    
    Write-Host "`nDownloading the Azure Egress Assessment script..." -ForegroundColor Blue
    
    # In production, this would download from a real URL
    try {
        Invoke-WebRequest -Uri $scriptUrl -OutFile $scriptPath -UseBasicParsing
        Write-Host "Assessment script downloaded successfully." -ForegroundColor Green
    } catch {
        Write-Host "Error downloading the script: $_" -ForegroundColor Red
        exit 1
    }
}

# Function to check if Azure PowerShell module is installed
function Check-AzureModules {
    Write-Host "`nChecking Azure PowerShell modules..." -ForegroundColor Blue
    
    $azModuleInstalled = Get-Module -ListAvailable -Name Az -ErrorAction SilentlyContinue
    
    if (-not $azModuleInstalled) {
        Write-Host "Azure PowerShell module not found." -ForegroundColor Yellow
        Write-Host "The script will try to use other authentication methods, but Az module is recommended." -ForegroundColor Yellow
        
        $installAzModule = Read-Host "Do you want to install the Az module? (y/n)"
        if ($installAzModule -eq 'y') {
            try {
                Install-Module -Name Az -AllowClobber -Scope CurrentUser -Force
                Write-Host "Azure PowerShell module installed successfully." -ForegroundColor Green
                $azModuleInstalled = $true
            } catch {
                Write-Host "Error installing Az module: $_" -ForegroundColor Red
                Write-Host "Continuing without Az module..." -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "Azure PowerShell module found." -ForegroundColor Green
    }
    
    # Check if logged in
    if ($azModuleInstalled) {
        try {
            $context = Get-AzContext -ErrorAction SilentlyContinue
            
            if (-not $context) {
                Write-Host "You are not logged into Azure PowerShell. Please log in:" -ForegroundColor Yellow
                Connect-AzAccount
                
                $context = Get-AzContext -ErrorAction SilentlyContinue
                if (-not $context) {
                    Write-Host "Azure login failed. The script will try to use other authentication methods." -ForegroundColor Yellow
                } else {
                    Write-Host "Azure PowerShell login successful." -ForegroundColor Green
                }
            } else {
                Write-Host "Already logged in as $($context.Account) to subscription $($context.Subscription.Name)" -ForegroundColor Green
            }
        } catch {
            Write-Host "Error checking Azure login: $_" -ForegroundColor Yellow
            Write-Host "The script will try to use other authentication methods." -ForegroundColor Yellow
        }
    }
}

# Function to run the assessment
function Run-Assessment {
    param (
        [string]$pythonExe,
        [string[]]$args
    )
    
    Write-Host "`nRunning Azure Default Egress Assessment..." -ForegroundColor Blue
    Write-Host "This may take several minutes depending on the size of your Azure environment.`n" -ForegroundColor Blue
    
    if (Test-Path $scriptPath) {
        Write-Host "Using script at: $scriptPath" -ForegroundColor Green
        & $pythonExe $scriptPath $args
    } else {
        Write-Host "Error: Assessment script not found at $scriptPath" -ForegroundColor Red
        exit 1
    }
}

# Function to install Python if it's not found
function Install-Python {
    Write-Host "Python 3.6+ is required but not found." -ForegroundColor Red
    Write-Host "Attempting to install Python 3..." -ForegroundColor Yellow
    
    try {
        # Check if Chocolatey is installed
        if (-not (Test-CommandExists "choco")) {
            Write-Host "Chocolatey not found. Installing Chocolatey..." -ForegroundColor Yellow
            
            # Install Chocolatey
            Set-ExecutionPolicy Bypass -Scope Process -Force
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
            Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
            
            if (-not (Test-CommandExists "choco")) {
                Write-Host "Failed to install Chocolatey. Please install Python 3.6+ manually: https://www.python.org/downloads/" -ForegroundColor Red
                return $null
            }
        }
        
        # Install Python using Chocolatey
        Write-Host "Installing Python 3 using Chocolatey..." -ForegroundColor Yellow
        choco install python -y
        
        # Refresh environment variables
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        
        # Check if Python is now available
        $pythonExe = Get-PythonExecutable
        if ($pythonExe) {
            Write-Host "Python installed successfully." -ForegroundColor Green
            return $pythonExe
        } else {
            Write-Host "Python installation failed. Please install Python 3.6+ manually: https://www.python.org/downloads/" -ForegroundColor Red
            return $null
        }
    } catch {
        Write-Host "Error installing Python: $_" -ForegroundColor Red
        Write-Host "Please install Python 3.6+ manually: https://www.python.org/downloads/" -ForegroundColor Yellow
        return $null
    }
}

# Main script execution
function Main {
    param (
        [Parameter(ValueFromRemainingArguments=$true)]
        [string[]]$ScriptArgs
    )
    
    # Check for Python 3.6+
    $pythonExe = Get-PythonExecutable
    
    if (-not $pythonExe) {
        $pythonExe = Install-Python
        
        if (-not $pythonExe) {
            exit 1
        }
    }
    
    # Check Python version
    if (-not (Test-PythonVersion $pythonExe)) {
        $currentVersion = & $pythonExe --version 2>&1
        Write-Host "Error: Python 3.6+ is required." -ForegroundColor Red
        Write-Host "Current version: $currentVersion" -ForegroundColor Yellow
        exit 1
    } else {
        $currentVersion = & $pythonExe --version
        Write-Host "Found $currentVersion" -ForegroundColor Green
    }
    
    # If running from URL without download, use the embedded script
    if (-not (Test-Path $scriptPath)) {
        Download-Script
    } else {
        Write-Host "Using local assessment script: $scriptPath" -ForegroundColor Green
    }
    
    # Install required packages
    Install-Packages $pythonExe
    
    # Check Azure modules
    Check-AzureModules
    
    # Run the assessment
    Run-Assessment $pythonExe $ScriptArgs
}

# Execute main with all args
Main $args
