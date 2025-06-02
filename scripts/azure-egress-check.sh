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
    if command_exists python3; then
        echo "python3"
    elif command_exists python && [[ $(python --version 2>&1) == *"Python 3"* ]]; then
        echo "python"
    else
        echo ""
    fi
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

# Function to install packages using pip
install_packages() {
    local python_exe=$1
    local pip_exe="${python_exe} -m pip"

    echo -e "\n${BLUE}Checking and installing required Python packages...${NC}"

    # Check if pip exists
    if ! $python_exe -m pip --version &> /dev/null; then
        echo -e "${YELLOW}pip not found. Attempting to install pip...${NC}"
        if command_exists curl; then
            curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
            $python_exe get-pip.py --user
            rm get-pip.py
        elif command_exists wget; then
            wget https://bootstrap.pypa.io/get-pip.py
            $python_exe get-pip.py --user
            rm get-pip.py
        else
            echo -e "${RED}Error: Neither curl nor wget found. Please install pip manually.${NC}"
            exit 1
        fi
    fi

    # Update pip
    echo -e "${BLUE}Updating pip...${NC}"
    $python_exe -m pip install --upgrade pip --quiet

    # Install each required package
    for package in "${REQUIREMENTS[@]}"; do
        echo -e "${BLUE}Installing $package...${NC}"
        $python_exe -m pip install --upgrade $package --quiet
    done

    echo -e "${GREEN}All required packages installed successfully.${NC}"
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
        echo -e "${YELLOW}Attempting to install Python 3...${NC}"
        
        # Try to install Python based on the platform
        if command_exists apt-get; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip
        elif command_exists yum; then
            sudo yum install -y python3 python3-pip
        elif command_exists brew; then
            brew install python
        else
            echo -e "${RED}Error: Could not install Python automatically.${NC}"
            echo -e "${YELLOW}Please install Python 3.6+ manually:${NC}"
            echo -e "${YELLOW}    https://www.python.org/downloads/${NC}"
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
    
    # Install required packages
    install_packages "$PYTHON_EXE"
    
    # Check Azure login status
    check_azure_login
    
    # Run the assessment
    run_assessment "$PYTHON_EXE" "$@"
}

# Execute main with all args
main "$@"
