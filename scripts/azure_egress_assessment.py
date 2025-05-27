#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure Default Egress Assessment Tool
===================================

This tool helps assess the impact of Azure's upcoming change to default internet egress
by identifying resources that rely on the default Azure internet routing.

Author: Aviatrix Systems, Inc.
Copyright © 2025 Aviatrix Systems, Inc. All rights reserved.
"""

import os
import sys
import json
import csv
import argparse
import datetime
import time
import re
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Set, Optional, Tuple, Union

# Try to import Azure libraries, provide helpful error if not installed
try:
    from azure.identity import AzureCliCredential, DefaultAzureCredential
    from azure.mgmt.resource import ResourceManagementClient
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.subscription import SubscriptionClient
    from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
except ImportError:
    print("Error: Required Azure libraries not found.")
    print("Please install required packages using: pip install azure-identity azure-mgmt-resource azure-mgmt-network azure-mgmt-subscription")
    sys.exit(1)

# Try to import Jinja2 for template rendering
try:
    from jinja2 import Template, FileSystemLoader, Environment
except ImportError:
    print("Error: Jinja2 library not found.")
    print("Please install Jinja2 using: pip install Jinja2")
    sys.exit(1)

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class AzureEgressAssessment:
    """Main class for Azure Default Egress Assessment Tool"""
    
    def __init__(self, args):
        """Initialize the assessment tool with command-line arguments"""
        self.args = args
        self.credential = None
        self.subscription_client = None
        self.subscriptions = []
        self.assessment_data = {}
        self.start_time = datetime.datetime.now()
        self.report_filename = f"azure-egress-assessment-{self.start_time.strftime('%Y%m%d-%H%M%S')}"
        
        # Template path - look for template in templates subfolder
        self.template_path = os.path.join(os.path.dirname(__file__), 'templates', 'report_template.html')
        if not os.path.exists(self.template_path):
            # Fallback to current directory
            self.template_path = os.path.join(os.path.dirname(__file__), 'report_template.html')
        
        # Progress tracking
        self.total_resources = 0
        self.processed_resources = 0
        self.last_progress_update = time.time()
        
    def authenticate(self):
        """Authenticate using Azure credentials"""
        print(f"{Colors.HEADER}Authenticating with Azure...{Colors.ENDC}")
        try:
            # First try Azure CLI credentials as they're most likely to be used
            self.credential = AzureCliCredential()
            # Test the credential
            self.subscription_client = SubscriptionClient(self.credential)
            next(self.subscription_client.subscriptions.list())
            print(f"{Colors.GREEN}✓ Authentication successful using Azure CLI credentials{Colors.ENDC}")
        except (ClientAuthenticationError, StopIteration) as e:
            print(f"{Colors.YELLOW}! Azure CLI authentication failed, trying DefaultAzureCredential...{Colors.ENDC}")
            try:
                # Fall back to DefaultAzureCredential
                self.credential = DefaultAzureCredential()
                self.subscription_client = SubscriptionClient(self.credential)
                next(self.subscription_client.subscriptions.list())
                print(f"{Colors.GREEN}✓ Authentication successful using DefaultAzureCredential{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.RED}✗ Authentication failed: {str(e)}{Colors.ENDC}")
                print("Please ensure you are logged in with 'az login' or have appropriate environment variables set.")
                sys.exit(1)
                
    def get_subscriptions(self):
        """Get a list of accessible Azure subscriptions"""
        print(f"{Colors.HEADER}Retrieving accessible subscriptions...{Colors.ENDC}")
        
        try:
            subscription_list = list(self.subscription_client.subscriptions.list())
            
            if not subscription_list:
                print(f"{Colors.YELLOW}! No subscriptions found. Please check your permissions.{Colors.ENDC}")
                sys.exit(1)
                
            # Filter subscriptions based on command line args if provided
            if self.args.subscription_id:
                subscription_ids = self.args.subscription_id.split(',')
                self.subscriptions = [sub for sub in subscription_list if sub.subscription_id in subscription_ids]
                if not self.subscriptions:
                    print(f"{Colors.RED}✗ No matching subscriptions found for ID(s): {self.args.subscription_id}{Colors.ENDC}")
                    sys.exit(1)
            else:
                self.subscriptions = subscription_list
                
            print(f"{Colors.GREEN}✓ Found {len(self.subscriptions)} accessible subscription(s){Colors.ENDC}")
            
            # Initialize assessment data structure
            for sub in self.subscriptions:
                self.assessment_data[sub.subscription_id] = {
                    'subscription_id': sub.subscription_id,
                    'display_name': sub.display_name,
                    'state': sub.state,
                    'vnets': {}
                }
            
        except Exception as e:
            print(f"{Colors.RED}✗ Failed to retrieve subscriptions: {str(e)}{Colors.ENDC}")
            sys.exit(1)
    
    def update_progress(self):
        """Update the progress indicator"""
        self.processed_resources += 1
        current_time = time.time()
        
        # Only update progress every 0.5 seconds to avoid screen flicker
        if current_time - self.last_progress_update >= 0.5:
            if self.total_resources > 0:
                percent = (self.processed_resources / self.total_resources) * 100
                sys.stdout.write(f"\r{Colors.CYAN}Progress: {self.processed_resources}/{self.total_resources} resources processed ({percent:.1f}%){Colors.ENDC}")
                sys.stdout.flush()
                self.last_progress_update = current_time
    
    def scan_subscription(self, subscription):
        """Scan a single subscription for resources"""
        sub_id = subscription.subscription_id
        sub_name = subscription.display_name
        print(f"\n{Colors.HEADER}Scanning subscription: {sub_name} ({sub_id}){Colors.ENDC}")
        
        try:
            # Initialize clients for this subscription
            resource_client = ResourceManagementClient(self.credential, sub_id)
            network_client = NetworkManagementClient(self.credential, sub_id)
            
            # Get all VNets in the subscription
            vnets = list(network_client.virtual_networks.list_all())
            
            if not vnets:
                print(f"{Colors.YELLOW}! No VNets found in subscription {sub_name}{Colors.ENDC}")
                return
            
            print(f"{Colors.GREEN}✓ Found {len(vnets)} VNets in subscription {sub_name}{Colors.ENDC}")
            
            # Update total resources for progress tracking
            self.total_resources += len(vnets)
            
            # Process each VNet
            for vnet in vnets:
                self.process_vnet(network_client, vnet, sub_id)
            
        except Exception as e:
            print(f"{Colors.RED}✗ Error scanning subscription {sub_name}: {str(e)}{Colors.ENDC}")
    
    def process_vnet(self, network_client, vnet, subscription_id):
        """Process a single VNet to check for default egress usage"""
        vnet_name = vnet.name
        resource_group = self._extract_resource_group(vnet.id)
        
        try:
            print(f"{Colors.CYAN}  Processing VNet: {vnet_name} (RG: {resource_group}){Colors.ENDC}")
            
            # Get subnets in this VNet
            subnets = vnet.subnets
            
            # Initialize VNet data structure
            self.assessment_data[subscription_id]['vnets'][vnet.id] = {
                'name': vnet_name,
                'id': vnet.id,
                'resource_group': resource_group,
                'address_space': [prefix for prefix in vnet.address_space.address_prefixes] if vnet.address_space else [],
                'subnets': {},
                'route_tables_count': 0,
                'subnets_count': len(subnets),
                'affected_subnets_count': 0
            }
            
            # Process subnets
            for subnet in subnets:
                self.process_subnet(network_client, subnet, vnet, subscription_id)
            
            # Count route tables
            unique_route_tables = set()
            for subnet_id, subnet_data in self.assessment_data[subscription_id]['vnets'][vnet.id]['subnets'].items():
                if subnet_data.get('route_table_id'):
                    unique_route_tables.add(subnet_data['route_table_id'])
            
            self.assessment_data[subscription_id]['vnets'][vnet.id]['route_tables_count'] = len(unique_route_tables)
            
            # Flag VNets with insufficient route tables for NVA redundancy
            if len(unique_route_tables) < 2:
                self.assessment_data[subscription_id]['vnets'][vnet.id]['insufficient_route_tables'] = True
            else:
                self.assessment_data[subscription_id]['vnets'][vnet.id]['insufficient_route_tables'] = False
            
            self.update_progress()
            
        except Exception as e:
            print(f"{Colors.RED}    ✗ Error processing VNet {vnet_name}: {str(e)}{Colors.ENDC}")
            self.update_progress()
    
    def process_subnet(self, network_client, subnet, vnet, subscription_id):
        """Process a single subnet to check for default egress usage"""
        subnet_name = subnet.name
        
        try:
            # Check for Route Table
            route_table_id = subnet.route_table.id if subnet.route_table else None
            
            # Check for NAT Gateway
            nat_gateway_id = subnet.nat_gateway.id if hasattr(subnet, 'nat_gateway') and subnet.nat_gateway else None
            
            # Initialize subnet data
            subnet_data = {
                'name': subnet_name,
                'id': subnet.id,
                'address_prefix': subnet.address_prefix,
                'route_table_id': route_table_id,
                'nat_gateway_id': nat_gateway_id,
                'network_interfaces': [],
                'has_default_route': False,
                'uses_default_egress': True,  # Assume using default egress until proven otherwise
                'classification': 'Not Affected'  # Default classification
            }
            
            # Check if route table has a default route (0.0.0.0/0)
            if route_table_id:
                try:
                    route_table_name = route_table_id.split('/')[-1]
                    resource_group = self._extract_resource_group(route_table_id)
                    route_table = network_client.route_tables.get(resource_group, route_table_name)
                    
                    for route in route_table.routes:
                        if route.address_prefix == '0.0.0.0/0':
                            subnet_data['has_default_route'] = True
                            subnet_data['uses_default_egress'] = False
                            subnet_data['default_route_next_hop'] = route.next_hop_type
                            break
                except Exception as e:
                    print(f"{Colors.YELLOW}      ! Error fetching route table for subnet {subnet_name}: {str(e)}{Colors.ENDC}")
            
            # If we have a NAT Gateway, subnet does not use default egress
            if nat_gateway_id:
                subnet_data['uses_default_egress'] = False
            
            # Get NICs in this subnet
            nic_count = 0
            nic_with_public_ip_count = 0
            resource_group = self._extract_resource_group(vnet.id)
            
            # Get all NICs in the resource group and filter by subnet
            for nic in network_client.network_interfaces.list(resource_group):
                for ip_config in nic.ip_configurations:
                    # Check if this NIC is in our current subnet
                    if ip_config.subnet and ip_config.subnet.id == subnet.id:
                        nic_count += 1
                        
                        # Check if NIC has a public IP
                        has_public_ip = ip_config.public_ip_address is not None
                        if has_public_ip:
                            nic_with_public_ip_count += 1
                        
                        # Store NIC info
                        subnet_data['network_interfaces'].append({
                            'id': nic.id,
                            'name': nic.name,
                            'private_ip': ip_config.private_ip_address,
                            'has_public_ip': has_public_ip,
                            'public_ip_id': ip_config.public_ip_address.id if has_public_ip else None
                        })
            
            # Determine classification based on NICs and egress status
            if not subnet_data['uses_default_egress'] or nic_count == 0:
                subnet_data['classification'] = 'Not Affected'
            elif nic_with_public_ip_count == 0 or nic_with_public_ip_count == nic_count:
                subnet_data['classification'] = 'Quick Remediation'
                self.assessment_data[subscription_id]['vnets'][vnet.id]['affected_subnets_count'] += 1
            else:
                subnet_data['classification'] = 'Mixed-Mode'
                self.assessment_data[subscription_id]['vnets'][vnet.id]['affected_subnets_count'] += 1
            
            # Add subnet data to assessment
            self.assessment_data[subscription_id]['vnets'][vnet.id]['subnets'][subnet.id] = subnet_data
            
            # Print classification with color
            classification = subnet_data['classification']
            if classification == 'Not Affected':
                classification_color = Colors.GREEN
            elif classification == 'Quick Remediation':
                classification_color = Colors.YELLOW
            else:
                classification_color = Colors.RED
                
            print(f"    Subnet: {subnet_name} - {classification_color}{classification}{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.RED}    ✗ Error processing subnet {subnet_name}: {str(e)}{Colors.ENDC}")
    
    def run_assessment(self):
        """Run the complete assessment workflow"""
        try:
            # Authenticate and get subscriptions
            self.authenticate()
            self.get_subscriptions()
            
            # Scan all subscriptions
            for subscription in self.subscriptions:
                self.scan_subscription(subscription)
                
            # Complete progress indicator
            print(f"\n{Colors.GREEN}✓ Assessment complete!{Colors.ENDC}")
            
            # Generate reports
            self.generate_terminal_summary()
            self.generate_html_report()
            
            # Generate exports if requested
            if self.args.export_json:
                self.export_json()
            if self.args.export_csv:
                self.export_csv()
                
        except Exception as e:
            print(f"{Colors.RED}✗ Assessment failed: {str(e)}{Colors.ENDC}")
            if self.args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    
    def generate_terminal_summary(self):
        """Generate a summary of findings in the terminal"""
        print(f"\n{Colors.HEADER}==================== ASSESSMENT SUMMARY ===================={Colors.ENDC}")
        
        # Calculate totals
        total_vnets = 0
        total_subnets = 0
        total_affected_subnets = 0
        total_quick_remediation = 0
        total_mixed_mode = 0
        total_not_affected = 0
        total_vnets_insufficient_rt = 0
        
        # Process each subscription
        for sub_id, sub_data in self.assessment_data.items():
            sub_vnets = len(sub_data['vnets'])
            sub_affected_subnets = 0
            sub_quick_remediation = 0
            sub_mixed_mode = 0
            sub_not_affected = 0
            sub_vnets_insufficient_rt = 0
            sub_subnets = 0
            
            # Calculate per-subscription metrics
            for vnet_id, vnet_data in sub_data['vnets'].items():
                sub_subnets += len(vnet_data['subnets'])
                sub_affected_subnets += vnet_data['affected_subnets_count']
                
                if vnet_data.get('insufficient_route_tables', False):
                    sub_vnets_insufficient_rt += 1
                
                # Count by classification
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    if subnet_data['classification'] == 'Not Affected':
                        sub_not_affected += 1
                    elif subnet_data['classification'] == 'Quick Remediation':
                        sub_quick_remediation += 1
                    elif subnet_data['classification'] == 'Mixed-Mode':
                        sub_mixed_mode += 1
            
            # Add to totals
            total_vnets += sub_vnets
            total_subnets += sub_subnets
            total_affected_subnets += sub_affected_subnets
            total_quick_remediation += sub_quick_remediation
            total_mixed_mode += sub_mixed_mode
            total_not_affected += sub_not_affected
            total_vnets_insufficient_rt += sub_vnets_insufficient_rt
            
            # Print subscription summary
            print(f"\n{Colors.BOLD}Subscription: {sub_data['display_name']} ({sub_id}){Colors.ENDC}")
            print(f"  VNets: {sub_vnets}")
            print(f"  Subnets: {sub_subnets}")
            print(f"  Affected Subnets: {sub_affected_subnets}")
            print(f"  VNets with Insufficient Route Tables: {sub_vnets_insufficient_rt}")
            print(f"  Classification:")
            print(f"    {Colors.GREEN}Not Affected: {sub_not_affected}{Colors.ENDC}")
            print(f"    {Colors.YELLOW}Quick Remediation: {sub_quick_remediation}{Colors.ENDC}")
            print(f"    {Colors.RED}Mixed-Mode: {sub_mixed_mode}{Colors.ENDC}")
        
        # Print overall summary
        print(f"\n{Colors.HEADER}==================== OVERALL SUMMARY ===================={Colors.ENDC}")
        print(f"Total Subscriptions: {len(self.assessment_data)}")
        print(f"Total VNets: {total_vnets}")
        print(f"Total Subnets: {total_subnets}")
        print(f"Total Affected Subnets: {total_affected_subnets}")
        print(f"Total VNets with Insufficient Route Tables: {total_vnets_insufficient_rt}")
        print(f"Classification:")
        print(f"  {Colors.GREEN}Not Affected: {total_not_affected}{Colors.ENDC}")
        print(f"  {Colors.YELLOW}Quick Remediation: {total_quick_remediation}{Colors.ENDC}")
        print(f"  {Colors.RED}Mixed-Mode: {total_mixed_mode}{Colors.ENDC}")
        
        # Print output locations
        print(f"\n{Colors.HEADER}==================== REPORTS ===================={Colors.ENDC}")
        print(f"HTML Report: {Colors.UNDERLINE}{self.report_filename}.html{Colors.ENDC}")
        if self.args.export_json:
            print(f"JSON Export: {Colors.UNDERLINE}{self.report_filename}.json{Colors.ENDC}")
        if self.args.export_csv:
            print(f"CSV Export: {Colors.UNDERLINE}{self.report_filename}.csv{Colors.ENDC}")
    
    def generate_html_report(self):
        """Generate a detailed HTML report using the template"""
        print(f"\n{Colors.HEADER}Generating HTML report...{Colors.ENDC}")
        
        try:
            # Check if template exists
            if not os.path.exists(self.template_path):
                print(f"{Colors.RED}✗ Template not found at: {self.template_path}{Colors.ENDC}")
                print(f"{Colors.YELLOW}! Falling back to inline HTML generation{Colors.ENDC}")
                return self._generate_fallback_html_report()
            
            # Calculate summary statistics
            template_data = self._prepare_template_data()
            
            # Load and render template
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            template = Template(template_content)
            html_content = template.render(**template_data)
            
            # Write HTML report
            with open(f"{self.report_filename}.html", "w", encoding='utf-8') as f:
                f.write(html_content)
                
            print(f"{Colors.GREEN}✓ HTML report generated: {self.report_filename}.html{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.RED}✗ Error generating HTML report: {str(e)}{Colors.ENDC}")
            if self.args.verbose:
                import traceback
                traceback.print_exc()
            
            # Try fallback generation
            print(f"{Colors.YELLOW}! Attempting fallback HTML generation{Colors.ENDC}")
            self._generate_fallback_html_report()
    
    def _prepare_template_data(self):
        """Prepare data for template rendering"""
        # Calculate summary statistics
        total_vnets = 0
        total_subnets = 0
        total_affected_subnets = 0
        total_quick_remediation = 0
        total_mixed_mode = 0
        total_not_affected = 0
        total_vnets_insufficient_rt = 0
        
        for sub_id, sub_data in self.assessment_data.items():
            sub_vnets = len(sub_data['vnets'])
            total_vnets += sub_vnets
            
            for vnet_id, vnet_data in sub_data['vnets'].items():
                vnet_subnets = len(vnet_data['subnets'])
                total_subnets += vnet_subnets
                total_affected_subnets += vnet_data['affected_subnets_count']
                
                if vnet_data.get('insufficient_route_tables', False):
                    total_vnets_insufficient_rt += 1
                
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    if subnet_data['classification'] == 'Not Affected':
                        total_not_affected += 1
                    elif subnet_data['classification'] == 'Quick Remediation':
                        total_quick_remediation += 1
                    elif subnet_data['classification'] == 'Mixed-Mode':
                        total_mixed_mode += 1
        
        # Calculate impact percentage
        impact_percentage = 0
        if total_subnets > 0:
            impact_percentage = round((total_affected_subnets / total_subnets) * 100, 1)
        
        # Generate table rows and content
        subnet_impact_rows = self._generate_subnet_impact_rows()
        subscription_summary_rows = self._generate_subscription_summary_rows()
        subscription_details = self._generate_subscription_details()
        
        # Prepare template data
        template_data = {
            'generated_date': self.start_time.strftime('%B %d, %Y at %I:%M %p'),
            'last_updated': self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'subscriptions_count': len(self.assessment_data),
            'total_vnets': total_vnets,
            'total_subnets': total_subnets,
            'impact_percentage': impact_percentage,
            'total_affected_subnets': total_affected_subnets,
            'total_not_affected': total_not_affected,
            'total_quick_remediation': total_quick_remediation,
            'total_mixed_mode': total_mixed_mode,
            'subnet_impact_rows': subnet_impact_rows,
            'subscription_summary_rows': subscription_summary_rows,
            'subscription_details': subscription_details
        }
        
        return template_data
    
    def _generate_subnet_impact_rows(self):
        """Generate HTML table rows for subnet impact analysis"""
        rows = []
        
        for sub_id, sub_data in self.assessment_data.items():
            for vnet_id, vnet_data in sub_data['vnets'].items():
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    classification = subnet_data['classification']
                    
                    # Determine risk level and remediation based on classification
                    if classification == 'Not Affected':
                        risk_level = 'None'
                        remediation = 'No action needed'
                        classification_class = 'status-not-affected'
                        risk_class = 'risk-none'
                    elif classification == 'Quick Remediation':
                        risk_level = 'Medium'
                        remediation = 'Add route table with default route or NAT Gateway'
                        classification_class = 'status-quick-remediation'
                        risk_class = 'risk-medium'
                    else:  # Mixed-Mode
                        risk_level = 'High'
                        remediation = 'Review and plan mixed-mode migration'
                        classification_class = 'status-mixed-mode'
                        risk_class = 'risk-high'
                    
                    row = f"""
                    <tr>
                        <td>{sub_data['display_name']}</td>
                        <td>{subnet_data['name']}</td>
                        <td>{vnet_data['name']}</td>
                        <td><span class="status-badge {classification_class}">{classification}</span></td>
                        <td><span class="{risk_class}">{risk_level}</span></td>
                        <td>{remediation}</td>
                    </tr>"""
                    rows.append(row)
        
        return '\n'.join(rows)
    
    def _generate_subscription_summary_rows(self):
        """Generate HTML table rows for subscription summary"""
        rows = []
        
        for sub_id, sub_data in self.assessment_data.items():
            vnets_total = len(sub_data['vnets'])
            vnets_affected = 0
            vnets_not_affected = 0
            
            for vnet_id, vnet_data in sub_data['vnets'].items():
                if vnet_data['affected_subnets_count'] > 0:
                    vnets_affected += 1
                else:
                    vnets_not_affected += 1
            
            impact_percentage = (vnets_affected / vnets_total * 100) if vnets_total > 0 else 0
            
            row = f"""
            <tr>
                <td>{sub_data['display_name']}</td>
                <td>{vnets_total}</td>
                <td>{vnets_affected}</td>
                <td>{vnets_not_affected}</td>
                <td>{impact_percentage:.1f}%</td>
            </tr>"""
            rows.append(row)
        
        return '\n'.join(rows)
    
    def _generate_subscription_details(self):
        """Generate collapsible subscription details content"""
        details = []
        
        for sub_id, sub_data in self.assessment_data.items():
            sub_name = sub_data['display_name']
            sub_vnets = len(sub_data['vnets'])
            
            detail_section = f"""
            <button class="collapsible">Subscription: {sub_name} ({sub_id}) - {sub_vnets} VNets</button>
            <div class="collapsible-content">
                <div class="section-content">"""
            
            # Add VNet details
            for vnet_id, vnet_data in sub_data['vnets'].items():
                vnet_name = vnet_data['name']
                resource_group = vnet_data['resource_group']
                address_space = ", ".join(vnet_data['address_space'])
                subnets_count = len(vnet_data['subnets'])
                affected_count = vnet_data['affected_subnets_count']
                route_tables_count = vnet_data['route_tables_count']
                insufficient_rt = vnet_data.get('insufficient_route_tables', False)
                
                detail_section += f"""
                <div class="vnet-detail">
                    <h4>{vnet_name}</h4>
                    <p><strong>Resource Group:</strong> {resource_group}</p>
                    <p><strong>Address Space:</strong> {address_space}</p>
                    <p><strong>Subnets:</strong> {subnets_count} total, {affected_count} affected</p>
                    <p><strong>Route Tables:</strong> {route_tables_count} 
                        {f'<span class="status-badge status-insufficient-rt">Insufficient for NVA Redundancy</span>' if insufficient_rt else ''}
                    </p>"""
                
                if subnets_count > 0:
                    detail_section += """
                    <h5>Subnets</h5>
                    <ul>"""
                    
                    # Add subnet details
                    for subnet_id, subnet_data in vnet_data['subnets'].items():
                        subnet_name = subnet_data['name']
                        classification = subnet_data['classification']
                        address_prefix = subnet_data['address_prefix']
                        
                        if classification == 'Not Affected':
                            classification_class = 'status-not-affected'
                        elif classification == 'Quick Remediation':
                            classification_class = 'status-quick-remediation'
                        else:
                            classification_class = 'status-mixed-mode'
                        
                        detail_section += f"""
                        <li>{subnet_name} ({address_prefix}): <span class="status-badge {classification_class}">{classification}</span></li>"""
                    
                    detail_section += """
                    </ul>"""
                
                detail_section += """
                </div>"""
            
            detail_section += """
                </div>
            </div>"""
            
            details.append(detail_section)
        
        return '\n'.join(details)
    
    def _generate_fallback_html_report(self):
        """Generate HTML report using the old inline method when template is not available"""
        print(f"{Colors.YELLOW}! Using fallback HTML generation{Colors.ENDC}")
        
        try:
            # Calculate summary statistics
            total_vnets = 0
            total_subnets = 0
            total_affected_subnets = 0
            total_quick_remediation = 0
            total_mixed_mode = 0
            total_not_affected = 0
            total_vnets_insufficient_rt = 0
            
            for sub_id, sub_data in self.assessment_data.items():
                sub_vnets = len(sub_data['vnets'])
                total_vnets += sub_vnets
                
                for vnet_id, vnet_data in sub_data['vnets'].items():
                    vnet_subnets = len(vnet_data['subnets'])
                    total_subnets += vnet_subnets
                    total_affected_subnets += vnet_data['affected_subnets_count']
                    
                    if vnet_data.get('insufficient_route_tables', False):
                        total_vnets_insufficient_rt += 1
                    
                    for subnet_id, subnet_data in vnet_data['subnets'].items():
                        if subnet_data['classification'] == 'Not Affected':
                            total_not_affected += 1
                        elif subnet_data['classification'] == 'Quick Remediation':
                            total_quick_remediation += 1
                        elif subnet_data['classification'] == 'Mixed-Mode':
                            total_mixed_mode += 1
            
            # Generate HTML content using the existing method
            html_content = self._generate_html_content(
                total_vnets, total_subnets, total_affected_subnets,
                total_quick_remediation, total_mixed_mode, total_not_affected,
                total_vnets_insufficient_rt
            )
            
            # Write HTML report
            with open(f"{self.report_filename}.html", "w", encoding='utf-8') as f:
                f.write(html_content)
                
            print(f"{Colors.GREEN}✓ Fallback HTML report generated: {self.report_filename}.html{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.RED}✗ Error generating fallback HTML report: {str(e)}{Colors.ENDC}")
            if self.args.verbose:
                import traceback
                traceback.print_exc()
    
    def _generate_html_content(self, total_vnets, total_subnets, total_affected_subnets,
                              total_quick_remediation, total_mixed_mode, total_not_affected,
                              total_vnets_insufficient_rt):
        """Generate the actual HTML content for the report"""
        
        # Generate current date/time
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate percentages for charts
        affected_percent = 0
        if total_subnets > 0:
            affected_percent = (total_affected_subnets / total_subnets) * 100
        
        quick_remediation_percent = 0
        mixed_mode_percent = 0
        not_affected_percent = 0
        if total_subnets > 0:
            quick_remediation_percent = (total_quick_remediation / total_subnets) * 100
            mixed_mode_percent = (total_mixed_mode / total_subnets) * 100
            not_affected_percent = (total_not_affected / total_subnets) * 100
        
        # Start HTML template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Azure Default Egress Assessment Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #fff;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background-color: #0072C6;
            color: white;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .summary {{
            background-color: #f9f9f9;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            grid-gap: 20px;
        }}
        .summary-box {{
            background-color: #fff;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
            text-align: center;
        }}
        .summary-box h3 {{
            margin-top: 0;
            color: #0072C6;
        }}
        .summary-box .number {{
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .chart-container {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .chart {{
            background-color: #fff;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
            flex: 1;
            min-width: 300px;
            height: 400px;
            display: flex;
            flex-direction: column;
        }}
        .chart h3 {{
            margin-top: 0;
            margin-bottom: 20px;
            color: #0072C6;
            text-align: center;
        }}
        .chart canvas {{
            flex: 1;
            width: 100% !important;
            height: 100% !important;
        }}
        .subscription {{
            background-color: #f9f9f9;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
        }}
        .vnet {{
            background-color: #fff;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
        }}
        .subnet {{
            background-color: #f9f9f9;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
        }}
        .classification {{
            padding: 5px 10px;
            border-radius: 3px;
            font-weight: bold;
            display: inline-block;
        }}
        .not-affected {{
            background-color: #DFF0D8;
            color: #3C763D;
        }}
        .quick-remediation {{
            background-color: #FCF8E3;
            color: #8A6D3B;
        }}
        .mixed-mode {{
            background-color: #F2DEDE;
            color: #A94442;
        }}
        .insufficient-rt {{
            background-color: #D9EDF7;
            color: #31708F;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        table th, table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        table th {{
            background-color: #f2f2f2;
        }}
        .collapsible {{
            background-color: #eee;
            color: #444;
            cursor: pointer;
            padding: 18px;
            width: 100%;
            border: none;
            text-align: left;
            outline: none;
            font-size: 15px;
            margin-bottom: 1px;
            border-radius: 5px;
        }}
        .active, .collapsible:hover {{
            background-color: #ccc;
        }}
        .content {{
            padding: 0 18px;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.2s ease-out;
            background-color: white;
            margin-bottom: 10px;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #777;
            font-size: 14px;
        }}
        .remediation {{
            background-color: #e8f5e9;
            padding: 15px;
            margin-top: 10px;
            border-radius: 5px;
            border-left: 5px solid #66bb6a;
        }}
        .remediation h4 {{
            margin-top: 0;
            color: #2e7d32;
        }}
        @media (max-width: 768px) {{
            .chart {{
                width: 100%;
            }}
        }}
    </style>
    <!-- Include Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Azure Default Egress Assessment Report</h1>
            <p>Generated on {now}</p>
        </div>
        
        <div class="summary">
            <h2>Executive Summary</h2>
            <p>This report provides an assessment of the impact of Azure's upcoming change to default internet egress on your environment.</p>
            
            <div class="summary-grid">
                <div class="summary-box">
                    <h3>Subscriptions</h3>
                    <div class="number">{len(self.assessment_data)}</div>
                </div>
                <div class="summary-box">
                    <h3>Virtual Networks</h3>
                    <div class="number">{total_vnets}</div>
                </div>
                <div class="summary-box">
                    <h3>Subnets</h3>
                    <div class="number">{total_subnets}</div>
                </div>
            </div>
            
            <h3>Subnet Impact and Classification</h3>
            <table>
                <tr>
                    <th>Subscription</th>
                    <th>Subnet Name</th>
                    <th>VNET Name</th>
                    <th>Classification</th>
                    <th>Risk Level</th>
                    <th>Recommended Remediation</th>
                </tr>"""
        # Add rows for each subnet across all subscriptions
        for sub_id, sub_data in self.assessment_data.items():
            for vnet_id, vnet_data in sub_data['vnets'].items():
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    classification = subnet_data['classification']
                    
                    # Determine risk level and remediation based on classification
                    if classification == 'Not Affected':
                        risk_level = 'Low'
                        remediation = 'No action needed'
                        classification_class = 'not-affected'
                    elif classification == 'Quick Remediation':
                        risk_level = 'Medium'
                        remediation = 'Add route table with default route'
                        classification_class = 'quick-remediation'
                    else:
                        risk_level = 'High'
                        remediation = 'Review and plan mixed-mode migration'
                        classification_class = 'mixed-mode'
                    
                    html += f"""
                <tr>
                    <td>{sub_data['display_name']}</td>
                    <td>{subnet_data['name']}</td>
                    <td>{vnet_data['name']}</td>
                    <td><span class="classification {classification_class}">{classification}</span></td>
                    <td>{risk_level}</td>
                    <td>{remediation}</td>
                </tr>"""
                    
        html += """
            </table>
            
            <h3>Subscription Summary</h3>
            <table>
                <tr>
                    <th>Subscription</th>
                    <th>Total VNETs</th>
                    <th>VNETs Needing Remediation</th>
                    <th>VNETs Not Affected</th>
                    <th>Impact Percentage</th>
                </tr>"""
        # Add rows for each subscription's VNET summary
        for sub_id, sub_data in self.assessment_data.items():
            vnets_total = len(sub_data['vnets'])
            vnets_affected = 0
            vnets_not_affected = 0
            
            for vnet_id, vnet_data in sub_data['vnets'].items():
                if vnet_data['affected_subnets_count'] > 0:
                    vnets_affected += 1
                else:
                    vnets_not_affected += 1
            
            impact_percentage = (vnets_affected / vnets_total * 100) if vnets_total > 0 else 0
            
            html += f"""
                <tr>
                    <td>{sub_data['display_name']}</td>
                    <td>{vnets_total}</td>
                    <td>{vnets_affected}</td>
                    <td>{vnets_not_affected}</td>
                    <td>{impact_percentage:.1f}%</td>
                </tr>"""
                    
        html += """
            </table>
        </div>
        
        <div class="chart-container">
            <div class="chart">
                <h3>Impact Assessment</h3>
                <canvas id="impactChart"></canvas>
            </div>
            <div class="chart">
                <h3>Classification Distribution</h3>
                <canvas id="classificationChart"></canvas>
            </div>
        </div>
        
        <div class="remediation">
            <h4>Remediation Guidance</h4>
            <p><strong>For Quick Remediation Subnets:</strong> Add a route table with a default route (0.0.0.0/0) or deploy a NAT Gateway.</p>
            <p><strong>For Mixed-Mode Subnets:</strong> Consider restructuring the subnet to separate resources with public IPs from those without, or implement a consistent connectivity strategy.</p>
            <p><strong>For VNets with Insufficient Route Tables:</strong> Add additional route tables to ensure proper NVA load balancing.</p>
        </div>

    <!-- Subscription Details -->"""
        
        # Add subscription details
        for sub_id, sub_data in self.assessment_data.items():
            sub_name = sub_data['display_name']
            sub_vnets = len(sub_data['vnets'])
            
            html += f"""
        <button class="collapsible">Subscription: {sub_name} ({sub_id}) - {sub_vnets} VNets</button>
        <div class="content">
"""
            
            # Add VNet details
            for vnet_id, vnet_data in sub_data['vnets'].items():
                vnet_name = vnet_data['name']
                resource_group = vnet_data['resource_group']
                address_space = ", ".join(vnet_data['address_space'])
                subnets_count = len(vnet_data['subnets'])
                affected_count = vnet_data['affected_subnets_count']
                route_tables_count = vnet_data['route_tables_count']
                insufficient_rt = vnet_data.get('insufficient_route_tables', False)
                
                html += f"""
            <div class="vnet">
                <h3>VNet: {vnet_name}</h3>
                <p><strong>Resource Group:</strong> {resource_group}</p>
                <p><strong>Address Space:</strong> {address_space}</p>
                <p><strong>Subnets:</strong> {subnets_count} total, {affected_count} affected</p>
                <p><strong>Route Tables:</strong> {route_tables_count} 
                    {f'<span class="classification insufficient-rt">Insufficient for NVA Redundancy</span>' if insufficient_rt else ''}
                </p>
"""
                
                if subnets_count > 0:
                    html += """
                <h4>Subnets</h4>
                <table>
                    <tr>
                        <th>Subnet Name</th>
                        <th>Address Prefix</th>
                        <th>Classification</th>
                        <th>Route Table</th>
                        <th>NAT Gateway</th>
                        <th>NICs</th>
                    </tr>
"""
                    
                    # Add subnet details
                    for subnet_id, subnet_data in vnet_data['subnets'].items():
                        subnet_name = subnet_data['name']
                        address_prefix = subnet_data['address_prefix']
                        classification = subnet_data['classification']
                        route_table_id = subnet_data.get('route_table_id', 'None')
                        nat_gateway_id = subnet_data.get('nat_gateway_id', 'None')
                        nics_count = len(subnet_data['network_interfaces'])
                        nics_with_public_ip = sum(1 for nic in subnet_data['network_interfaces'] if nic['has_public_ip'])
                        
                        classification_class = ""
                        if classification == "Not Affected":
                            classification_class = "not-affected"
                        elif classification == "Quick Remediation":
                            classification_class = "quick-remediation"
                        else:
                            classification_class = "mixed-mode"
                        
                        route_table_name = "None"
                        if route_table_id is not None and route_table_id != "None":
                            route_table_name = route_table_id.split('/')[-1]
                            
                        nat_gateway_name = "None"
                        if nat_gateway_id is not None and nat_gateway_id != "None":
                            nat_gateway_name = nat_gateway_id.split('/')[-1]
                        
                        html += f"""
                    <tr>
                        <td>{subnet_name}</td>
                        <td>{address_prefix}</td>
                        <td><span class="classification {classification_class}">{classification}</span></td>
                        <td>{route_table_name}</td>
                        <td>{nat_gateway_name}</td>
                        <td>{nics_count} ({nics_with_public_ip} with public IP)</td>
                    </tr>
"""
                    
                    html += """
                </table>
"""
                
                html += """
            </div>
"""
            
            html += """
        </div>
"""
        
        # Complete the HTML template
        html += """
        <div class="footer">
            <p>Azure Default Egress Assessment Tool</p>
            <p>Copyright © 2025 Aviatrix Systems, Inc. All rights reserved.</p>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Initialize collapsible sections
            var coll = document.getElementsByClassName("collapsible");
            var i;
            
            for (i = 0; i < coll.length; i++) {
                coll[i].addEventListener("click", function() {
                    this.classList.toggle("active");
                    var content = this.nextElementSibling;
                    if (content.style.maxHeight) {
                        content.style.maxHeight = null;
                    } else {
                        content.style.maxHeight = content.scrollHeight + "px";
                    } 
                });
            }
        });

        // Charts
        window.onload = function() {
            // Common chart options
            const commonOptions = {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                layout: {
                    padding: 20
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                            pointStyle: 'circle'
                        }
                    },
                    title: {
                        display: true,
                        font: {
                            size: 16,
                            weight: 'bold'
                        },
                        padding: {
                            top: 10,
                            bottom: 30
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        titleFont: {
                            size: 14
                        },
                        bodyFont: {
                            size: 13
                        },
                        padding: 12,
                        cornerRadius: 6,
                        displayColors: true
                    }
                }
            };

            // Impact Chart
            var impactCtx = document.getElementById('impactChart').getContext('2d');
            var impactChart = new Chart(impactCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Affected', 'Not Affected'],
                    datasets: [{
                        data: [
""" + f"{total_affected_subnets}, {total_subnets - total_affected_subnets}" + """],
                        backgroundColor: ['#f8d7da', '#d4edda'],
                        borderWidth: 1,
                        borderColor: 'white'
                    }]
                },
                options: {
                    ...commonOptions,
                    plugins: {
                        ...commonOptions.plugins,
                        title: {
                            ...commonOptions.plugins.title,
                            text: 'Subnet Impact Assessment'
                        },
                        tooltip: {
                            ...commonOptions.plugins.tooltip,
                            callbacks: {
                                label: function(context) {
                                    const value = context.raw;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${context.label}: ${value} subnets (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
            
            // Classification Chart
            var classCtx = document.getElementById('classificationChart').getContext('2d');
            var classChart = new Chart(classCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Not Affected', 'Quick Remediation', 'Mixed-Mode'],
                    datasets: [{
                        data: [""" + f"{total_not_affected}, {total_quick_remediation}, {total_mixed_mode}" + """],
                        backgroundColor: ['#d4edda', '#fff3cd', '#f8d7da'],
                        borderWidth: 1,
                        borderColor: 'white'
                    }]
                },
                options: {
                    ...commonOptions,
                    plugins: {
                        ...commonOptions.plugins,
                        title: {
                            ...commonOptions.plugins.title,
                            text: 'Subnet Classification Distribution'
                        },
                        tooltip: {
                            ...commonOptions.plugins.tooltip,
                            callbacks: {
                                label: function(context) {
                                    const value = context.raw;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${context.label}: ${value} subnets (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        };
    </script>
</body>
</html>
"""
        
        return html
    
    def export_json(self):
        """Export assessment data to JSON file"""
        print(f"{Colors.HEADER}Exporting JSON data...{Colors.ENDC}")
        
        try:
            with open(f"{self.report_filename}.json", "w") as f:
                # Convert to serializable format
                export_data = {
                    'metadata': {
                        'generated_at': self.start_time.isoformat(),
                        'tool_version': '1.0.0',
                    },
                    'assessment': self.assessment_data
                }
                
                json.dump(export_data, f, indent=2)
                
            print(f"{Colors.GREEN}✓ JSON data exported: {self.report_filename}.json{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.RED}✗ Error exporting JSON data: {str(e)}{Colors.ENDC}")
    
    def export_csv(self):
        """Export assessment data to CSV file"""
        print(f"{Colors.HEADER}Exporting CSV data...{Colors.ENDC}")
        
        try:
            with open(f"{self.report_filename}.csv", "w", newline='') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([
                    'Subscription ID', 'Subscription Name', 
                    'VNet Name', 'Resource Group', 'Address Space',
                    'Subnet Name', 'Address Prefix', 'Classification',
                    'Uses Default Egress', 'Has Route Table', 'Has Default Route',
                    'Has NAT Gateway', 'NICs Count', 'NICs With Public IP'
                ])
                
                # Write data rows
                for sub_id, sub_data in self.assessment_data.items():
                    sub_name = sub_data['display_name']
                    
                    for vnet_id, vnet_data in sub_data['vnets'].items():
                        vnet_name = vnet_data['name']
                        resource_group = vnet_data['resource_group']
                        address_space = ", ".join(vnet_data['address_space'])
                        
                        for subnet_id, subnet_data in vnet_data['subnets'].items():
                            subnet_name = subnet_data['name']
                            address_prefix = subnet_data['address_prefix']
                            classification = subnet_data['classification']
                            uses_default_egress = subnet_data['uses_default_egress']
                            has_route_table = subnet_data['route_table_id'] is not None
                            has_default_route = subnet_data.get('has_default_route', False)
                            has_nat_gateway = subnet_data['nat_gateway_id'] is not None
                            nics_count = len(subnet_data['network_interfaces'])
                            nics_with_public_ip = sum(1 for nic in subnet_data['network_interfaces'] if nic['has_public_ip'])
                            
                            writer.writerow([
                                sub_id, sub_name,
                                vnet_name, resource_group, address_space,
                                subnet_name, address_prefix, classification,
                                uses_default_egress, has_route_table, has_default_route,
                                has_nat_gateway, nics_count, nics_with_public_ip
                            ])
                
            print(f"{Colors.GREEN}✓ CSV data exported: {self.report_filename}.csv{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.RED}✗ Error exporting CSV data: {str(e)}{Colors.ENDC}")
    
    def _extract_resource_group(self, resource_id: str) -> str:
        """Extract resource group name from Azure resource ID"""
        match = re.search(r'/resourceGroups/([^/]+)', resource_id)
        if match:
            return match.group(1)
        return ""

def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Azure Default Egress Assessment Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python azure_egress_assessment.py                      # Scan all subscriptions
  python azure_egress_assessment.py --subscription-id SUB1,SUB2  # Scan specific subscriptions
  python azure_egress_assessment.py --export-json --export-csv    # Export data in JSON and CSV formats
  python azure_egress_assessment.py --verbose            # Show detailed logs
        """
    )
    
    parser.add_argument('--subscription-id', 
                        help='Comma-separated list of subscription IDs to scan')
    parser.add_argument('--export-json', action='store_true',
                        help='Export assessment data to JSON file')
    parser.add_argument('--export-csv', action='store_true',
                        help='Export assessment data to CSV file')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed logs and error messages')
    
    return parser.parse_args()

def main():
    """Main entry point"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}Azure Default Egress Assessment Tool{Colors.ENDC}")
    print(f"{Colors.CYAN}Copyright © 2025 Aviatrix Systems, Inc. All rights reserved.{Colors.ENDC}\n")
    
    args = parse_arguments()
    assessment = AzureEgressAssessment(args)
    assessment.run_assessment()

if __name__ == "__main__":
    main()
