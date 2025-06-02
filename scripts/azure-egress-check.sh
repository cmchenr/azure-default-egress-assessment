#!/usr/bin/env bash
#
# Azure Default Egress Assessment Tool - Bash Launcher Script
# Copyright © 2025 Aviatrix Systems, Inc. All rights reserved.
#
# This script checks for Python, installs required packages, and runs the Azure Egress Assessment tool.

set -e

# ANSI color codes
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Script variables
# GitHub repository information
GITHUB_REPO="cmchenr/azure-default-egress-assessment"
GITHUB_BRANCH="main"
# URLs for script download
SCRIPT_URL="https://raw.githubusercontent.com/$GITHUB_REPO/$GITHUB_BRANCH/scripts/azure_egress_assessment.py"
TEMPLATE_URL="https://raw.githubusercontent.com/$GITHUB_REPO/$GITHUB_BRANCH/scripts/templates/report_template.html"
# Temp directory and file paths for downloaded files
TEMP_DIR="$(mktemp -d -t azure_egress_assessment.XXXXXX)"
SCRIPT_PATH="$TEMP_DIR/azure_egress_assessment.py"
TEMPLATE_PATH="$TEMP_DIR/report_template.html"
VENV_PATH="$TEMP_DIR/venv"
REQUIREMENTS=(
    "azure-identity"
    "azure-mgmt-resource"
    "azure-mgmt-network"
    "azure-mgmt-subscription"
)

# Print banner
echo -e "${BLUE}${BOLD}"
echo "======================================================"
echo "    Azure Default Egress Assessment Tool - Launcher   "
echo "======================================================"
echo -e "${NC}"
echo -e "Copyright © 2025 Aviatrix Systems, Inc. All rights reserved.\n"

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to get Python executable
get_python_executable() {
    # Try python3 first (preferred)
    if command_exists python3; then
        echo "python3"
        return
    fi
    
    # Try python if it's Python 3
    if command_exists python && [[ $(python --version 2>&1) == *"Python 3"* ]]; then
        echo "python"
        return
    fi
    
    # On macOS, check for common Homebrew paths
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # Check Homebrew Intel path
        if [ -f "/usr/local/bin/python3" ]; then
            echo "/usr/local/bin/python3"
            return
        fi
        
        # Check Homebrew Apple Silicon path
        if [ -f "/opt/homebrew/bin/python3" ]; then
            echo "/opt/homebrew/bin/python3"
            return
        fi
        
        # Check for pyenv or other version managers
        if command_exists pyenv && pyenv global >/dev/null 2>&1; then
            local pyenv_python="$(pyenv which python3 2>/dev/null)"
            if [ -n "$pyenv_python" ] && [ -f "$pyenv_python" ]; then
                echo "$pyenv_python"
                return
            fi
        fi
    fi
    
    echo ""
}

# Function to check Python version
check_python_version() {
    local python_exe=$1
    local python_version=$($python_exe --version 2>&1 | cut -d ' ' -f 2)
    local major=$(echo "$python_version" | cut -d '.' -f 1)
    local minor=$(echo "$python_version" | cut -d '.' -f 2)
    
    if [[ "$major" -lt 3 ]] || ([[ "$major" -eq 3 ]] && [[ "$minor" -lt 6 ]]); then
        return 1
    else
        return 0
    fi
}

# Function to create virtual environment and install packages
setup_virtual_environment() {
    local python_exe=$1

    echo -e "\n${BLUE}Creating virtual environment for package isolation...${NC}"
    echo -e "${BLUE}This avoids conflicts with system Python packages.${NC}"

    # Create virtual environment
    echo -e "${BLUE}Creating virtual environment at: $VENV_PATH${NC}"
    if ! $python_exe -m venv "$VENV_PATH" 2>/dev/null; then
        echo -e "${YELLOW}Failed to create virtual environment. This might be due to missing venv module.${NC}"
        
        # Detect operating system and provide appropriate guidance
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            echo -e "${BLUE}Detected macOS. Checking Python installation...${NC}"
            echo -e "${YELLOW}On macOS, venv should be included with Python 3.3+${NC}"
            
            if command_exists brew; then
                echo -e "${BLUE}Homebrew detected. You might want to try:${NC}"
                echo -e "${YELLOW}  brew install python3${NC}"
                echo -e "${YELLOW}Or ensure you're using Homebrew Python:${NC}"
                echo -e "${YELLOW}  which python3${NC}"
            else
                echo -e "${YELLOW}Consider installing Homebrew and Python via Homebrew:${NC}"
                echo -e "${YELLOW}  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"${NC}"
                echo -e "${YELLOW}  brew install python3${NC}"
            fi
            
            echo -e "${RED}Error: Cannot create virtual environment on macOS.${NC}"
            echo -e "${YELLOW}Please ensure you have a working Python 3.6+ installation.${NC}"
            exit 1
            
        elif command_exists apt-get; then
            echo -e "${BLUE}Installing python3-venv (Ubuntu/Debian)...${NC}"
            sudo apt-get update && sudo apt-get install -y python3-venv
        elif command_exists yum; then
            echo -e "${BLUE}Installing python3-venv (RHEL/CentOS)...${NC}"
            sudo yum install -y python3-venv
        elif command_exists dnf; then
            echo -e "${BLUE}Installing python3-venv (Fedora)...${NC}"
            sudo dnf install -y python3-venv
        else
            echo -e "${RED}Error: Could not install venv module automatically.${NC}"
            echo -e "${YELLOW}Please install manually based on your OS:${NC}"
            echo -e "${YELLOW}  Ubuntu/Debian: sudo apt-get install python3-venv${NC}"
            echo -e "${YELLOW}  RHEL/CentOS:   sudo yum install python3-venv${NC}"
            echo -e "${YELLOW}  Fedora:        sudo dnf install python3-venv${NC}"
            echo -e "${YELLOW}  macOS:         brew install python3${NC}"
            exit 1
        fi
        
        # Try creating venv again (only for Linux systems)
        if [[ "$OSTYPE" != "darwin"* ]]; then
            if ! $python_exe -m venv "$VENV_PATH"; then
                echo -e "${RED}Error: Still unable to create virtual environment.${NC}"
                echo -e "${YELLOW}Please check your Python installation.${NC}"
                exit 1
            fi
        fi
    fi
    
    echo -e "${GREEN}✓ Virtual environment created successfully${NC}"

    # Activate virtual environment
    source "$VENV_PATH/bin/activate"
    
    # Get the virtual environment Python executable
    local venv_python="$VENV_PATH/bin/python"
    
    echo -e "${BLUE}Using virtual environment Python: $($venv_python --version)${NC}"

    # Update pip in virtual environment
    echo -e "${BLUE}Updating pip in virtual environment...${NC}"
    $venv_python -m pip install --upgrade pip --quiet

    # Install each required package in virtual environment
    echo -e "${BLUE}Installing required packages in virtual environment...${NC}"
    for package in "${REQUIREMENTS[@]}"; do
        echo -e "${BLUE}Installing $package...${NC}"
        if ! $venv_python -m pip install --upgrade $package --quiet; then
            echo -e "${RED}Error: Failed to install $package in virtual environment.${NC}"
            exit 1
        fi
    done

    echo -e "${GREEN}✓ All required packages installed successfully in virtual environment${NC}"
    
    # Return the virtual environment python path
    echo "$venv_python"
}

# Function to download the assessment script and template
download_script() {
    echo -e "\n${BLUE}Downloading the Azure Egress Assessment script and template from GitHub...${NC}"
    
    # Download the main script from GitHub
    if command_exists curl; then
        curl -s -L -o "$SCRIPT_PATH" "$SCRIPT_URL"
        curl -s -L -o "$TEMPLATE_PATH" "$TEMPLATE_URL"
    elif command_exists wget; then
        wget -q -O "$SCRIPT_PATH" "$SCRIPT_URL"
        wget -q -O "$TEMPLATE_PATH" "$TEMPLATE_URL"
    else
        echo -e "${RED}Error: Neither curl nor wget found. Cannot download the script.${NC}"
        exit 1
    fi
    
    if [ -f "$SCRIPT_PATH" ]; then
        chmod +x "$SCRIPT_PATH"
        echo -e "${GREEN}Assessment script downloaded successfully from GitHub.${NC}"
    else
        echo -e "${RED}Error: Failed to download the script from GitHub.${NC}"
        echo -e "${RED}URL: $SCRIPT_URL${NC}"
        exit 1
    fi
    
    if [ -f "$TEMPLATE_PATH" ]; then
        echo -e "${GREEN}Report template downloaded successfully from GitHub.${NC}"
    else
        echo -e "${RED}Error: Failed to download the template from GitHub.${NC}"
        echo -e "${RED}URL: $TEMPLATE_URL${NC}"
        exit 1
    fi
}

# Function to check if Azure CLI is logged in
check_azure_login() {
    echo -e "\n${BLUE}Checking Azure CLI login status...${NC}"
    
    if command_exists az; then
        if az account show &> /dev/null; then
            echo -e "${GREEN}Azure CLI is logged in.${NC}"
        else
            echo -e "${YELLOW}You are not logged into Azure CLI. Please log in:${NC}"
            az login
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}Azure login failed. Please make sure Azure CLI is properly installed and try again.${NC}"
                exit 1
            fi
            
            echo -e "${GREEN}Azure CLI login successful.${NC}"
        fi
    else
        echo -e "${YELLOW}Azure CLI not found. The script will try to use DefaultAzureCredential instead.${NC}"
        echo -e "${YELLOW}If authentication fails, please install Azure CLI with:${NC}"
        echo -e "${YELLOW}    https://docs.microsoft.com/en-us/cli/azure/install-azure-cli${NC}"
    fi
}

# Function to run the assessment
run_assessment() {
    local python_exe=$1
    shift
    local args=("$@")
    
    echo -e "\n${BLUE}Running Azure Default Egress Assessment...${NC}"
    echo -e "${BLUE}This may take several minutes depending on the size of your Azure environment.${NC}\n"
    
    # Execute the downloaded script
    $python_exe "$SCRIPT_PATH" "${args[@]}"
}

# Main script execution
main() {
    # Check for Python 3.6+
    PYTHON_EXE=$(get_python_executable)
    
    # Create a trap to clean up the temp directory on exit
    trap 'rm -rf "$TEMP_DIR"; echo -e "\n${BLUE}Cleaning up temporary files...${NC}"' EXIT
    
    if [ -z "$PYTHON_EXE" ]; then
        echo -e "${RED}Error: Python 3.6+ is required but not found.${NC}"
        
        # Provide OS-specific installation guidance
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo -e "${YELLOW}On macOS, you can install Python 3 using:${NC}"
            if command_exists brew; then
                echo -e "${BLUE}Installing Python via Homebrew...${NC}"
                brew install python
            else
                echo -e "${YELLOW}Option 1 - Install Homebrew first, then Python:${NC}"
                echo -e "${YELLOW}  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"${NC}"
                echo -e "${YELLOW}  brew install python${NC}"
                echo -e "${YELLOW}Option 2 - Download from python.org:${NC}"
                echo -e "${YELLOW}  https://www.python.org/downloads/macos/${NC}"
                exit 1
            fi
        elif command_exists apt-get; then
            echo -e "${BLUE}Installing Python via apt-get...${NC}"
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv
        elif command_exists yum; then
            echo -e "${BLUE}Installing Python via yum...${NC}"
            sudo yum install -y python3 python3-pip python3-venv
        elif command_exists dnf; then
            echo -e "${BLUE}Installing Python via dnf...${NC}"
            sudo dnf install -y python3 python3-pip python3-venv
        else
            echo -e "${RED}Error: Could not install Python automatically.${NC}"
            echo -e "${YELLOW}Please install Python 3.6+ manually based on your OS:${NC}"
            echo -e "${YELLOW}  macOS:         brew install python (after installing Homebrew)${NC}"
            echo -e "${YELLOW}  Ubuntu/Debian: sudo apt-get install python3 python3-venv${NC}"
            echo -e "${YELLOW}  RHEL/CentOS:   sudo yum install python3 python3-venv${NC}"
            echo -e "${YELLOW}  Or download from: https://www.python.org/downloads/${NC}"
            exit 1
        fi
        
        # Check again
        PYTHON_EXE=$(get_python_executable)
        
        if [ -z "$PYTHON_EXE" ]; then
            echo -e "${RED}Error: Python installation failed.${NC}"
            exit 1
        fi
    fi
    
    # Check Python version
    if ! check_python_version "$PYTHON_EXE"; then
        echo -e "${RED}Error: Python 3.6+ is required.${NC}"
        echo -e "${YELLOW}Current version: $($PYTHON_EXE --version)${NC}"
        exit 1
    else
        echo -e "${GREEN}Found $(${PYTHON_EXE} --version)${NC}"
    fi
    
    # Always download the latest script from GitHub
    download_script
    
    # Setup virtual environment and install required packages
    VENV_PYTHON=$(setup_virtual_environment "$PYTHON_EXE")
    
    # Check Azure login status
    check_azure_login
    
    # Run the assessment using virtual environment Python
    run_assessment "$VENV_PYTHON" "$@"
}

# Execute main with all args
main "$@"
