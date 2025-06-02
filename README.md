# Azure Default Egress Assessment Tool

A comprehensive assessment tool developed by Aviatrix to help Azure customers evaluate their exposure to Microsoft's upcoming default internet egress changes and plan their migration strategy.

## Sample Report

Get instant visibility into your Azure environment's egress configuration and security posture:

![Azure Egress Assessment Report](azure-egress-report-screenshot.png)

*Comprehensive Azure Default Egress Assessment Report showing executive summary, network analysis, and detailed remediation recommendations.*

## 🚀 Quick Launch

**🔒 100% Local Execution** - Uses your existing Azure credentials, no data transmitted to Aviatrix or external services.

### One-Line Execution

**macOS/Linux:**
```bash
curl -sSL https://raw.githubusercontent.com/cmchenr/azure-default-egress-assessment/main/scripts/azure-egress-check.sh | bash
```

**Windows PowerShell:**
```powershell
iwr -useb https://raw.githubusercontent.com/cmchenr/azure-default-egress-assessment/main/scripts/azure-egress-check.ps1 | iex
```

The tool will automatically:
- ✅ Install required dependencies
- ✅ Use your existing Azure CLI/PowerShell credentials  
- ✅ Scan all accessible subscriptions
- ✅ Generate comprehensive HTML report with timestamp
- ✅ Keep all data local on your system

## Understanding Azure's Default Egress Change

Microsoft Azure is retiring default outbound access for Virtual Machines, fundamentally changing how internet egress works in Virtual Networks. This change will impact resources that currently rely on Azure's automatic internet routing without explicit configuration.

### What is Default Egress?

Azure Default Egress is a feature that automatically provides internet connectivity to Virtual Machines without requiring explicit configuration. According to [Microsoft's decision tree](https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/default-outbound-access), a subnet uses default egress when:

1. **No Route Table Applied**: The subnet doesn't have a route table configured
2. **No Explicit Internet Route**: If a route table exists, it lacks an explicit 0.0.0.0/0 route
3. **No NAT Gateway**: The subnet doesn't have an Azure NAT Gateway configured
4. **Workloads Without Public IPs**: VMs in these subnets don't have public IP addresses assigned

### Impact and Timeline

While Microsoft has indicated that existing subnets and workloads may not be immediately affected, **new subnets** created in VNets without explicit egress configuration will lose internet connectivity. This makes it critical to prepare your VNets with proper egress mechanisms before creating new subnets.

### The Security Imperative

Beyond compliance with Azure's changes, addressing default egress represents a significant security improvement. Internet egress is the primary vector attackers use for:

- **Command & Control**: Establishing persistent communication channels
- **Data Exfiltration**: Stealing sensitive information from your environment  
- **Malware Download**: Retrieving additional attack tools and payloads
- **Botnet Participation**: Using compromised resources for distributed attacks

Implementing proper egress controls with firewall capabilities can prevent these attack vectors and significantly improve your security posture.

## Complex Migration Scenarios

### Mixed-Mode Subnets: The Primary Challenge

The most complex scenario involves subnets containing both VMs with public IPs and VMs using default egress. This creates asymmetric routing problems:

- **Outbound Traffic**: Follows User Defined Routes (UDRs) to your firewall
- **Return Traffic**: Attempts to route directly back to public IP addresses
- **Result**: Traffic drops due to asymmetric routing, breaking connectivity

**Solution Options:**
1. **Subnet Separation**: Split workloads into dedicated subnets (recommended)
2. **Public IP Removal**: Migrate public IPs to Azure Application Gateway with WAF
3. **Accept Risk**: Keep existing subnets unchanged if confirmed safe by Microsoft

### VNets with Overlapping CIDRs

Traditional hub-and-spoke architectures fail when VNets have overlapping CIDR ranges, as Azure VNET peering cannot connect multiple VNets with identical address spaces to the same hub.

**Traditional Challenges:**
- Cannot peer overlapping VNets to central firewall hub
- Azure Firewall in each VNet increases costs and complexity
- Custom NAT solutions mask traffic origin, limiting firewall rule granularity

**Aviatrix Solution:**
Aviatrix's distributed firewall architecture uniquely addresses this challenge with:
- **Global Policy Management**: Centralized rules across distributed firewalls
- **No Hub Dependency**: Each VNet maintains independent egress
- **Higher Availability**: Eliminates single points of failure
- **Cost Efficiency**: Reduces data transfer costs and complexity

## Assessment Tool Features

This comprehensive assessment tool analyzes your Azure environment to identify egress dependencies and provide actionable migration guidance:

### Core Analysis Capabilities

- **Multi-Subscription Discovery**: Automatically scans all accessible Azure subscriptions
- **VNet Classification**: Categorizes Virtual Networks based on egress readiness:
  - **Ready: Secure** - Firewalled egress with 0.0.0.0/0 UDRs detected
  - **Ready: Insecure** - NAT Gateway configured but no firewall protection
  - **Not Ready** - No explicit egress mechanism configured
- **Detailed Subnet Analysis**: Classifies each subnet's egress configuration:
  - **No Workloads** - Empty subnets with no impact
  - **Public Subnet** - All VMs have public IP addresses
  - **Azure NAT Gateway** - Explicit NAT Gateway configured
  - **UDR with 0.0.0.0/0** - Custom routing to firewall or appliance
  - **Affected: Default Egress** - Using Azure's automatic egress
  - **Affected: Mixed-Mode** - Combination of public IPs and default egress

### Advanced Analysis Features

- **Workload Risk Assessment**: Identifies VMs with direct public IP exposure
- **Route Table Intelligence**: Analyzes UDR next-hop destinations and correlates with network appliances
- **CIDR Overlap Detection**: Identifies VNets that cannot share a common hub due to address conflicts
- **Aviatrix Readiness Check**: Evaluates route table configuration for distributed firewall deployment
- **Remediation Prioritization**: Recommends action sequence based on complexity and risk

### Comprehensive Reporting

The tool generates multiple output formats for different stakeholders:

1. **Executive Dashboard**: High-level metrics and risk assessment
2. **Technical Analysis**: Detailed subnet-by-subnet breakdown
3. **Remediation Roadmap**: Prioritized action items with specific guidance
4. **Data Export**: JSON and CSV formats for further analysis

### Report Structure

**Executive Summary**
- Environment overview with key metrics
- Risk distribution across subscriptions
- High-level remediation recommendations

**Network Analysis**
- Visual charts showing VNet and subnet classifications
- CIDR overlap analysis
- Egress mechanism distribution

**Impact Assessment**
- Subscription-by-subscription breakdown
- VNet details with subnet composition
- Specific workload impact analysis

**Remediation Guidance**
- Scenario-specific recommendations
- Implementation complexity assessment
- Security enhancement opportunities

## 🔒 Security and Privacy Commitment

**100% Local Execution**: This tool runs entirely within your Azure environment using standard Azure APIs. No assessment data is transmitted to Aviatrix, external services, or third parties.

**Your Credentials, Your Control**: Uses your existing Azure CLI or PowerShell authentication. No additional sign-ups or credential sharing required.

**Read-Only Access**: Requires only standard read permissions to analyze your network configuration. No modifications are made to your environment.

**Complete Data Ownership**: All reports and data remain on your local system. You control all data sharing and distribution.

## Detailed Installation Options

### Prerequisites

- **Azure Access**: Account with read permissions across target subscriptions
- **Authentication**: Azure CLI (recommended) or PowerShell module configured  
- **Python**: Version 3.6 or higher (auto-installed if missing)
- **Internet Connection**: For downloading dependencies and script updates

### Alternative Installation Methods

#### Option 1: Download and Run

**Linux/macOS:**
```bash
# Download the script
curl -sSL https://raw.githubusercontent.com/cmchenr/azure-default-egress-assessment/main/scripts/azure-egress-check.sh -o azure-egress-check.sh

# Make executable and run
chmod +x azure-egress-check.sh
./azure-egress-check.sh
```

**Windows PowerShell:**
```powershell
# Download the script
Invoke-WebRequest -Uri https://raw.githubusercontent.com/cmchenr/azure-default-egress-assessment/main/scripts/azure-egress-check.ps1 -OutFile azure-egress-check.ps1

# Execute the assessment
./azure-egress-check.ps1
```

### Advanced Usage Options

Customize your assessment with additional parameters:

```bash
# Target specific subscriptions
./azure-egress-check.sh --subscription-id "sub1-uuid,sub2-uuid"

# Export detailed data for analysis
./azure-egress-check.sh --export-json --export-csv

# Enable verbose logging
./azure-egress-check.sh --verbose

# Combine multiple options
./azure-egress-check.sh --subscription-id "your-sub-id" --export-json --verbose
```

### What Happens When You Run It

1. **Environment Setup**: Automatically installs required Python dependencies
2. **Authentication**: Uses existing Azure CLI or PowerShell credentials
3. **Discovery**: Scans all accessible subscriptions for VNets and subnets
4. **Analysis**: Evaluates egress configurations and identifies risks
5. **Reporting**: Generates timestamped HTML report with detailed findings
6. **Output**: Displays summary in terminal with paths to detailed reports

## Remediation Strategies

### Immediate Actions for Different Scenarios

#### VNets Classified as "Not Ready"
**Issue**: No explicit egress mechanism configured
**Solutions**:
1. **Azure NAT Gateway** (Quick fix, limited security)
   - Provides immediate egress capability
   - Minimal security visibility and control
   - Best for development/testing environments

2. **Firewall with UDRs** (Recommended for production)
   - Route tables with 0.0.0.0/0 pointing to firewall
   - Azure Firewall, Aviatrix Cloud Firewall, or third-party NVAs
   - Enhanced security with traffic inspection and control

#### Mixed-Mode Subnets (High Priority)
**Issue**: Asymmetric routing breaks connectivity when adding UDRs
**Recommended Approach**:
1. **Inventory Analysis**: Document all VMs and their connectivity requirements
2. **Subnet Redesign**: Separate VMs by egress method into dedicated subnets  
3. **Public IP Migration**: Consider moving public IPs to Azure Application Gateway
4. **Staged Implementation**: Migrate in phases to minimize business impact

#### VNets with CIDR Overlaps
**Issue**: Cannot use traditional hub-and-spoke architecture
**Solutions**:
1. **Distributed Firewalls**: Deploy firewall in each VNet (Azure Firewall or Aviatrix)
2. **CIDR Readdressing**: Plan subnet migrations to eliminate overlaps (complex)
3. **Aviatrix Architecture**: Leverage distributed management without hub dependency

### Security Enhancement Recommendations

#### Replace NAT Gateway with Firewall
If your assessment shows "Ready: Insecure" VNets using NAT Gateways:

**Benefits of Firewall Upgrade**:
- **Threat Detection**: Identify malicious domains and suspicious traffic patterns
- **Data Loss Prevention**: Block unauthorized data exfiltration attempts  
- **Compliance**: Meet regulatory requirements for traffic inspection
- **Incident Response**: Detailed logs for security investigation

**Implementation Options**:
- **Azure Firewall**: Native integration with Azure services
- **Aviatrix Cloud Firewall**: Advanced distributed architecture with global management
- **Third-Party NVAs**: Solutions from Palo Alto, Fortinet, Check Point, etc.

#### Aviatrix Cloud Firewall Advantages

For organizations seeking optimal security and operational efficiency:

**Unique Capabilities**:
- **Distributed Architecture**: No single point of failure or bottleneck
- **Global Management**: Centralized policy across all VNets and clouds
- **CIDR Overlap Support**: Works with overlapping address spaces
- **Cost Optimization**: Eliminates data transfer charges between VNets
- **Advanced Visibility**: Application-level traffic analysis and control

**Ideal Scenarios**:
- Multi-VNet environments with complex connectivity requirements
- Organizations with CIDR overlap challenges
- Hybrid and multi-cloud deployments requiring consistent security
- Environments prioritizing high availability and performance

## Testing and Validation

### Terraform Test Environment

A comprehensive test environment is included to validate the assessment tool's accuracy and help you understand different egress scenarios.

**Located in**: `/terraform` directory

**Test Scenarios Deployed**:
- Default egress configuration (affected)
- NAT Gateway implementation (ready: insecure)  
- Route table with firewall UDR (ready: secure)
- Mixed-mode subnet with public IPs and default egress (high-risk)
- Multiple route tables for NVA load balancing
- Overlapping CIDR configurations
- Various workload distributions

### Deploying the Test Environment

```bash
cd terraform
./deploy_and_test.sh
```

This creates 8 different VNet configurations representing real-world scenarios you might encounter in your environment. After deployment, run the assessment tool to see how each scenario is classified and what recommendations are provided.

**Benefits of Testing**:
- Validate tool accuracy in a controlled environment
- Understand classification logic before running on production
- Practice remediation steps on test resources
- Verify firewall rules and routing changes

### Validating Results

After running the assessment on your test environment:

1. **Review Classifications**: Ensure each test VNet is classified correctly
2. **Test Remediation**: Practice implementing recommended changes  
3. **Verify Connectivity**: Confirm workloads maintain internet access after changes
4. **Monitor Security**: Test firewall rules and traffic visibility

## Output Formats and Data Export

### Generated Reports

**HTML Dashboard** (Primary Output)
- Interactive charts and visual analytics
- Drill-down capability for detailed investigation  
- Executive summary suitable for stakeholder presentations
- Technical details for implementation teams

**Terminal Output**
- Color-coded summary of findings
- Quick identification of high-priority issues
- Progress tracking during large environment scans

**JSON Export** (Optional: `--export-json`)
- Complete assessment data in structured format
- Integration with custom analysis tools
- Programmatic processing of results
- Backup of detailed findings

**CSV Export** (Optional: `--export-csv`)  
- Tabular format for spreadsheet analysis
- Easy filtering and sorting capabilities
- Integration with reporting tools
- Simplified data sharing

### Report Locations

All outputs are saved in the current directory with timestamps:
- `azure-egress-assessment-YYYYMMDD-HHMMSS.html`
- `azure-egress-assessment-YYYYMMDD-HHMMSS.json` (if requested)
- `azure-egress-assessment-YYYYMMDD-HHMMSS.csv` (if requested)

## Next Steps After Assessment

### 1. Review and Prioritize
- Focus on "Mixed-Mode" subnets first (highest complexity)
- Address "Not Ready" VNets before creating new subnets
- Plan security upgrades for "Ready: Insecure" NAT Gateway configurations

### 2. Plan Your Migration
- **Development/Test**: Start with non-production environments
- **Staging**: Validate remediation approaches before production implementation
- **Production**: Implement during planned maintenance windows

### 3. Consider Enhanced Security
If you're implementing new egress controls, consider upgrading beyond basic compliance:
- **Threat Intelligence**: Block known malicious destinations
- **Application Control**: Restrict access by application type and destination
- **Zero Trust**: Implement least-privilege access principles
- **Monitoring**: Establish baseline traffic patterns and alerts

### 4. Explore Aviatrix Solutions
For organizations seeking comprehensive cloud networking and security:

**Assessment and Consultation**: Contact Aviatrix for detailed architecture review
**Proof of Concept**: Deploy Aviatrix in a test environment to evaluate benefits
**Migration Planning**: Work with Aviatrix experts to design optimal architecture
**Training and Support**: Leverage Aviatrix's extensive documentation and support resources

## Additional Resources

### Microsoft Documentation
- [Azure Default Outbound Access Overview](https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/default-outbound-access)
- [Azure NAT Gateway Documentation](https://learn.microsoft.com/en-us/azure/virtual-network/nat-gateway/)
- [User Defined Routes (UDR) Guide](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-udr-overview)
- [Azure Firewall Documentation](https://learn.microsoft.com/en-us/azure/firewall/)

### Aviatrix Resources
- [Aviatrix Cloud Firewall](https://aviatrix.com/products/cloud-firewall/)
- [Azure Networking Best Practices](https://aviatrix.com/learn-center/cloud-architecture/)
- [Multi-Cloud Security Architecture](https://aviatrix.com/solutions/multi-cloud-security/)

## License and Support

**Copyright © 2025 Aviatrix Systems, Inc. All rights reserved.**

### Support Options

**Tool Issues**: For bugs or feature requests, please create an issue in the GitHub repository

**Azure Architecture Guidance**: Contact your Microsoft representative for Azure-specific questions

**Aviatrix Solutions**: Visit [aviatrix.com](https://aviatrix.com) or contact Aviatrix for networking and security consultation

**Emergency Support**: For critical production issues, contact your respective vendor support channels