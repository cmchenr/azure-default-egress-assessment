# Azure Default Egress Assessment Tool

A tool developed by Aviatrix to help customers assess the impact of Azure's upcoming change to default internet egress.

## Background

Microsoft Azure is planning to change how default internet egress works in Virtual Networks. This will impact resources that currently rely on the default Azure internet routing without explicit configuration. Signs of potential impact include:

1. Subnets without a route table applied
2. Subnets with a route table that doesn't have an explicit 0.0.0.0/0 route
3. Subnets without a NAT gateway configured
4. Workloads in these subnets without public IPs

This tool scans your Azure environment to identify potentially affected resources and generates a detailed report to help you plan your migration strategy.

## High-Risk Scenario

The most challenging scenario is a subnet with mixed workloads - some with public IPs, some without. These "mixed-use" subnets are flagged as high-risk in the report as they require careful planning for migration.

## Features

The assessment tool provides comprehensive analysis of your Azure environment:

- **Resource Discovery**: Automatically scans all accessible Azure subscriptions
- **Impact Assessment**: Identifies VNETs and subnets relying on default egress paths
- **Workload Analysis**: Classifies NICs as having public IPs or not for precise impact assessment
- **Classification**:
  - **Not Affected**: Subnets not using default egress or with no NICs
  - **Quick Remediation Ready**: Subnets using default egress where all NICs either have or don't have public IPs
  - **Mixed-Mode Remediation Required**: Subnets using default egress with a mix of NICs with and without public IPs
- **Route Table Analysis**: Detects VNETs with insufficient route tables for proper NVA load balancing
- **Detailed Reports**: Generates both terminal output and HTML reports
- **Export Options**: Export findings in JSON and CSV formats for further analysis
- **Remediation Guidance**: Provides actionable recommendations tailored to each scenario

## Output Formats

The tool produces several output formats:

1. **Terminal Output**: Color-coded console output showing affected resources
2. **HTML Report**: Detailed interactive report with comprehensive analysis
3. **JSON Export** (optional): Complete assessment data in structured JSON format
4. **CSV Export** (optional): Tabular summary for easy import into spreadsheets or databases

## Report Output

The tool generates an HTML report with the following information:

1. Executive summary with statistics on impacted resources
2. Detailed breakdown by subscription, VNet, and subnet
3. Lists of affected workloads
4. Recommendations for mitigation strategies

The report is saved in the current directory with a timestamp in the filename.

## Mitigation Recommendations

For affected subnets, the following mitigation strategies are recommended:

1. **Add explicit routing**: Create or update route tables with a 0.0.0.0/0 route pointing to a firewall, Virtual Network Appliance, or Azure Firewall
2. **Implement NAT Gateway**: Deploy a NAT Gateway for centralized outbound connectivity
3. **Reconfigure mixed-use subnets**: Either split into separate subnets or ensure all workloads have consistent connectivity patterns
4. **For proper NVA load balancing**: Ensure VNETs have at least 2 route tables configured

## Installation and Usage

The tool can be run using one of the following methods:

### Option 1: Direct Download and Run

1. Download the scripts from the repository
2. Run the appropriate launcher script for your operating system

#### For Linux/macOS:

```bash
# Download the script
curl -sSL https://example.com/azure-egress-check.sh -o azure-egress-check.sh

# Make it executable
chmod +x azure-egress-check.sh

# Run the assessment
./azure-egress-check.sh
```

#### For Windows:

```powershell
# Download the script
Invoke-WebRequest -Uri https://example.com/azure-egress-check.ps1 -OutFile azure-egress-check.ps1

# Run the assessment
./azure-egress-check.ps1
```

### Option 2: One-Line Execution

#### For Linux/macOS:

```bash
curl -sSL https://example.com/azure-egress-check.sh | bash
```

#### For Windows:

```powershell
iwr -useb https://example.com/azure-egress-check.ps1 | iex
```

### Advanced Usage Options

You can pass additional parameters to the assessment tool:

```bash
# Scan specific subscriptions only
./azure-egress-check.sh --subscription-id SUB1,SUB2

# Export results to JSON and CSV
./azure-egress-check.sh --export-json --export-csv

# Show verbose output
./azure-egress-check.sh --verbose
```

## Requirements

- Azure account with appropriate permissions to view resources
- Python 3.6 or higher (will be automatically installed if missing)
- Azure CLI (recommended) or Azure PowerShell module
- Internet connection to download the script and required Python packages

## Security and Privacy

This tool runs entirely within your own environment. No data is transmitted outside your Azure subscriptions. The tool uses standard Azure API calls to collect the information needed for the assessment.

## License

Copyright © 2025 Aviatrix Systems, Inc. All rights reserved.

## Support

For questions or support regarding this tool, please contact Aviatrix support or visit [aviatrix.com](https://aviatrix.com).