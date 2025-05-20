# Azure Default Egress Assessment Tool - Implementation Guide

## Overview

This document provides a comprehensive guide to the Azure Default Egress Assessment Tool, which helps customers assess the impact of Azure's upcoming change to default internet egress.

## Components

The tool consists of three main components:

1. **Core Python Script** (`azure_egress_assessment.py`)
2. **Bash Launcher Script** (`azure-egress-check.sh`) for Linux/macOS users
3. **PowerShell Launcher Script** (`azure-egress-check.ps1`) for Windows users

## Functionality

### Core Python Script

This script performs the actual assessment by:

- Scanning all accessible Azure subscriptions (or filtered ones)
- Identifying VNETs and subnets relying on default egress
- Classifying subnets based on their egress configuration
- Detecting NICs with and without public IPs
- Generating comprehensive reports in terminal, HTML, JSON, and CSV formats

#### Classification Logic:

- **Not Affected**: Subnets that have a NAT Gateway, an explicit 0.0.0.0/0 route, or no NICs
- **Quick Remediation Ready**: Subnets using default egress where all NICs either have public IPs or none have public IPs
- **Mixed-Mode Remediation Required**: Subnets using default egress with a mix of NICs with and without public IPs

### Launcher Scripts

Both launcher scripts (Bash and PowerShell) provide a user-friendly way to run the assessment by:

1. Checking for Python 3.6+
2. Installing required dependencies
3. Downloading the core Python script (in production)
4. Checking for Azure CLI authentication
5. Running the assessment tool with the user's parameters

## Usage

### Direct Python Usage

```bash
python azure_egress_assessment.py [options]
```

Options:
- `--subscription-id SUB1,SUB2`: Scan specific subscriptions
- `--export-json`: Export results to JSON
- `--export-csv`: Export results to CSV
- `--verbose`: Show detailed logs and error messages

### Bash Launcher Usage (Linux/macOS)

```bash
./azure-egress-check.sh [options]
```

### PowerShell Launcher Usage (Windows)

```powershell
./azure-egress-check.ps1 [options]
```

## Output Files

For each assessment, the following files are generated (with a timestamp):

1. `azure-egress-assessment-YYYYMMDD-HHMMSS.html`: Interactive HTML report with charts
2. `azure-egress-assessment-YYYYMMDD-HHMMSS.json`: JSON export (if requested)
3. `azure-egress-assessment-YYYYMMDD-HHMMSS.csv`: CSV export (if requested)

## Testing Results

The tool was successfully tested against an Azure environment with test VNets that simulate different scenarios:

- VNets with default egress and no additional routing
- VNets with route tables but no default route
- VNets with proper routing (explicit 0.0.0.0/0 route)
- VNets with NAT gateway
- VNets with insufficient route tables for NVA redundancy

The assessment correctly identified and classified all test scenarios.

## Deployment Notes

For production deployment:

1. Host the `azure_egress_assessment.py` script on a publicly accessible URL
2. Update the URL in both launcher scripts to point to this location
3. Provide users with the one-line commands for Linux/macOS and Windows

## One-Line Commands (Example for Production)

### Linux/macOS:
```bash
curl -sSL https://example.com/azure-egress-check.sh | bash
```

### Windows:
```powershell
iwr -useb https://example.com/azure-egress-check.ps1 | iex
```
