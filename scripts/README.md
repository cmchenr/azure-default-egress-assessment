# Azure Default Egress Assessment Scripts

This directory contains the core assessment script and launcher scripts for the Azure Default Egress Assessment Tool.

## Contents

- `azure_egress_assessment.py`: Core Python script that performs the Azure environment assessment
- `azure-egress-check.sh`: Bash launcher script for Linux/macOS environments
- `azure-egress-check.ps1`: PowerShell launcher script for Windows environments

## Usage

### Running the Python script directly

```bash
python azure_egress_assessment.py [options]
```

Available options:
- `--subscription-id SUB1,SUB2`: Scan specific subscriptions only
- `--export-json`: Export results to JSON format
- `--export-csv`: Export results to CSV format
- `--verbose`: Show detailed logs and error messages

### Using the launcher scripts

The launcher scripts handle all dependencies and requirements automatically.

#### On Linux/macOS:

```bash
./azure-egress-check.sh [options]
```

#### On Windows:

```powershell
./azure-egress-check.ps1 [options]
```

The options are passed through to the Python script.

## Requirements

- Python 3.6+
- Azure SDK for Python packages:
  - azure-identity
  - azure-mgmt-resource
  - azure-mgmt-network
  - azure-mgmt-subscription
- Authentication via Azure CLI or DefaultAzureCredential
