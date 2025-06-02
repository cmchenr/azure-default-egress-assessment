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
                'subnets_count': len(subnets),
                'classification': 'Not Ready',  # Default VNet classification
                'has_nat_gateway': False,
                'has_default_route_udr': False,
                'overlapping_cidrs': []
            }
            
            # Process subnets
            for subnet in subnets:
                self.process_subnet(network_client, subnet, vnet, subscription_id)
            
            # Analyze VNet-level capabilities and subnet classifications
            has_nat_gateway = False
            has_default_route_udr = False
            has_affected_subnets = False
            has_mixed_mode_subnets = False
            has_default_egress_subnets = False
            
            for subnet_id, subnet_data in self.assessment_data[subscription_id]['vnets'][vnet.id]['subnets'].items():
                if subnet_data.get('nat_gateway_id'):
                    has_nat_gateway = True
                if subnet_data.get('has_default_route'):
                    has_default_route_udr = True
                
                # Check subnet classifications to determine VNet impact
                subnet_classification = subnet_data.get('classification', 'Not Affected')
                if subnet_classification == 'Affected: Mixed-Mode':
                    has_affected_subnets = True
                    has_mixed_mode_subnets = True
                elif subnet_classification == 'Affected: Default Egress':
                    has_affected_subnets = True
                    has_default_egress_subnets = True
            
            self.assessment_data[subscription_id]['vnets'][vnet.id]['has_nat_gateway'] = has_nat_gateway
            self.assessment_data[subscription_id]['vnets'][vnet.id]['has_default_route_udr'] = has_default_route_udr
            
            # Classify VNet based on subnet impact and egress mechanisms detected
            if has_affected_subnets:
                # VNet has affected subnets, so it should be classified as affected
                self.assessment_data[subscription_id]['vnets'][vnet.id]['classification'] = 'Affected'
            else:
                # VNet has no affected subnets
                self.assessment_data[subscription_id]['vnets'][vnet.id]['classification'] = 'Not Affected'
            
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
                'default_route_next_hop': None,
                'default_route_next_hop_ip': None,
                'uses_default_egress': True,  # Assume using default egress until proven otherwise
                'classification': 'Not Affected',  # Default classification
                'egress_mechanism': 'Default',
                'reason': ''
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
                            subnet_data['egress_mechanism'] = 'UDR'
                            
                            # Try to get the next hop IP if it's a Virtual Appliance
                            if route.next_hop_type == 'VirtualAppliance' and hasattr(route, 'next_hop_ip_address'):
                                subnet_data['default_route_next_hop_ip'] = route.next_hop_ip_address
                            break
                except Exception as e:
                    print(f"{Colors.YELLOW}      ! Error fetching route table for subnet {subnet_name}: {str(e)}{Colors.ENDC}")
            
            # If we have a NAT Gateway, subnet does not use default egress
            if nat_gateway_id:
                subnet_data['uses_default_egress'] = False
                subnet_data['egress_mechanism'] = 'NAT Gateway'
            
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
            
            # New classification logic based on updated README
            if nic_count == 0:
                subnet_data['classification'] = 'Not Affected'
                subnet_data['reason'] = 'No Workloads'
            elif nic_with_public_ip_count == nic_count and nic_count > 0:
                # All workloads have public IPs
                subnet_data['classification'] = 'Not Affected'
                subnet_data['reason'] = 'Public Subnet'
            elif nat_gateway_id:
                # NAT Gateway present
                subnet_data['classification'] = 'Not Affected' 
                subnet_data['reason'] = 'Azure NAT Gateway'
            elif subnet_data['has_default_route']:
                # UDR with 0.0.0.0/0 route
                subnet_data['classification'] = 'Not Affected'
                subnet_data['reason'] = f"UDR with 0.0.0.0/0 ({subnet_data['default_route_next_hop']})"
            elif subnet_data['uses_default_egress']:
                # Using default egress - check for mixed mode
                if nic_with_public_ip_count > 0 and nic_with_public_ip_count < nic_count:
                    # Mixed mode: some NICs with public IPs, some without
                    subnet_data['classification'] = 'Affected: Mixed-Mode'
                    subnet_data['reason'] = 'Mixed mode subnet'
                else:
                    # All NICs either have or don't have public IPs
                    subnet_data['classification'] = 'Affected: Default Egress'
                    subnet_data['reason'] = 'Using default egress'
            else:
                subnet_data['classification'] = 'Not Affected'
                subnet_data['reason'] = 'Explicit egress configured'
            
            # Store workload counts in subnet data
            subnet_data['nic_count'] = nic_count
            subnet_data['public_ip_count'] = nic_with_public_ip_count
            
            # Add subnet data to assessment
            self.assessment_data[subscription_id]['vnets'][vnet.id]['subnets'][subnet.id] = subnet_data
            
            # Print classification with color
            classification = subnet_data['classification']
            if classification == 'Not Affected':
                classification_color = Colors.GREEN
            elif classification == 'Affected: Default Egress':
                classification_color = Colors.YELLOW
            else:  # Mixed-Mode
                classification_color = Colors.RED
                
            print(f"    Subnet: {subnet_name} - {classification_color}{classification}{Colors.ENDC} ({subnet_data['reason']})")
            
        except Exception as e:
            print(f"{Colors.RED}    ✗ Error processing subnet {subnet_name}: {str(e)}{Colors.ENDC}")
    
    def detect_cidr_overlaps(self):
        """Detect VNets with overlapping CIDR ranges that cannot be connected to the same hub"""
        import ipaddress
        
        print(f"{Colors.HEADER}Detecting CIDR overlaps...{Colors.ENDC}")
        
        # Collect all VNets with their CIDR ranges
        vnet_list = []
        for sub_id, sub_data in self.assessment_data.items():
            for vnet_id, vnet_data in sub_data['vnets'].items():
                for address_prefix in vnet_data['address_space']:
                    try:
                        network = ipaddress.ip_network(address_prefix, strict=False)
                        vnet_list.append({
                            'subscription_id': sub_id,
                            'subscription_name': sub_data['display_name'],
                            'vnet_id': vnet_id,
                            'vnet_name': vnet_data['name'],
                            'cidr': address_prefix,
                            'network': network
                        })
                    except ValueError as e:
                        print(f"{Colors.YELLOW}! Warning: Invalid CIDR {address_prefix} in VNet {vnet_data['name']}: {e}{Colors.ENDC}")
                        continue
        
        # Find overlapping CIDRs using network overlap detection
        overlaps_dict = {}
        overlaps_list = []
        
        for i, vnet1 in enumerate(vnet_list):
            for j, vnet2 in enumerate(vnet_list[i+1:], i+1):
                # Skip if same VNet
                if vnet1['vnet_id'] == vnet2['vnet_id']:
                    continue
                    
                # Check for overlap (either direction)
                network1 = vnet1['network']
                network2 = vnet2['network']
                
                if network1.overlaps(network2):
                    # Create overlap pair key for deduplication
                    pair_key = tuple(sorted([
                        f"{vnet1['subscription_id']}:{vnet1['vnet_id']}:{vnet1['cidr']}",
                        f"{vnet2['subscription_id']}:{vnet2['vnet_id']}:{vnet2['cidr']}"
                    ]))
                    
                    if pair_key not in overlaps_dict:
                        # Determine relationship (contains, contained, or partial overlap)
                        if network1.subnet_of(network2):
                            relationship = f"{vnet1['cidr']} is contained within {vnet2['cidr']}"
                        elif network2.subnet_of(network1):
                            relationship = f"{vnet2['cidr']} is contained within {vnet1['cidr']}"
                        else:
                            relationship = f"{vnet1['cidr']} and {vnet2['cidr']} partially overlap"
                        
                        overlap_info = {
                            'vnet1': vnet1,
                            'vnet2': vnet2,
                            'relationship': relationship
                        }
                        
                        overlaps_dict[pair_key] = overlap_info
                        overlaps_list.append(overlap_info)
                        
                        # Mark both VNets as having overlapping CIDRs
                        if 'overlapping_cidrs' not in self.assessment_data[vnet1['subscription_id']]['vnets'][vnet1['vnet_id']]:
                            self.assessment_data[vnet1['subscription_id']]['vnets'][vnet1['vnet_id']]['overlapping_cidrs'] = []
                        if 'overlapping_cidrs' not in self.assessment_data[vnet2['subscription_id']]['vnets'][vnet2['vnet_id']]:
                            self.assessment_data[vnet2['subscription_id']]['vnets'][vnet2['vnet_id']]['overlapping_cidrs'] = []
                            
                        self.assessment_data[vnet1['subscription_id']]['vnets'][vnet1['vnet_id']]['overlapping_cidrs'].append({
                            'vnet_name': vnet2['vnet_name'],
                            'vnet_id': vnet2['vnet_id'],
                            'subscription_name': vnet2['subscription_name'],
                            'subscription_id': vnet2['subscription_id'],
                            'cidr': vnet2['cidr'],
                            'relationship': relationship
                        })
                        
                        self.assessment_data[vnet2['subscription_id']]['vnets'][vnet2['vnet_id']]['overlapping_cidrs'].append({
                            'vnet_name': vnet1['vnet_name'],
                            'vnet_id': vnet1['vnet_id'],
                            'subscription_name': vnet1['subscription_name'],
                            'subscription_id': vnet1['subscription_id'],
                            'cidr': vnet1['cidr'],
                            'relationship': relationship
                        })
        
        # Store overlaps for template data
        self.cidr_overlaps = overlaps_list
        
        if overlaps_list:
            print(f"{Colors.YELLOW}! Found {len(overlaps_list)} CIDR overlap(s) across VNets{Colors.ENDC}")
            for overlap in overlaps_list:
                vnet1 = overlap['vnet1']
                vnet2 = overlap['vnet2']
                print(f"  {vnet1['vnet_name']} ({vnet1['subscription_name']}) - {vnet1['cidr']}")
                print(f"  {vnet2['vnet_name']} ({vnet2['subscription_name']}) - {vnet2['cidr']}")
                print(f"  Relationship: {overlap['relationship']}")
                print()
        else:
            print(f"{Colors.GREEN}✓ No CIDR overlaps detected{Colors.ENDC}")

    def run_assessment(self):
        """Run the complete assessment workflow"""
        try:
            # Authenticate and get subscriptions
            self.authenticate()
            self.get_subscriptions()
            
            # Scan all subscriptions
            for subscription in self.subscriptions:
                self.scan_subscription(subscription)
                
            # Detect CIDR overlaps
            self.detect_cidr_overlaps()
            
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
        total_default_egress = 0
        total_mixed_mode = 0
        total_not_affected = 0
        total_vnets_ready_secure = 0
        total_vnets_ready_insecure = 0
        total_vnets_not_ready = 0
        total_vnets_with_overlaps = 0
        total_subnets_no_workloads = 0
        total_subnets_public = 0
        total_subnets_nat_gateway = 0
        total_subnets_udr = 0
        
        # Process each subscription
        for sub_id, sub_data in self.assessment_data.items():
            sub_vnets = len(sub_data['vnets'])
            sub_affected_subnets = 0
            sub_default_egress = 0
            sub_mixed_mode = 0
            sub_not_affected = 0
            sub_subnets = 0
            sub_vnets_ready_secure = 0
            sub_vnets_ready_insecure = 0
            sub_vnets_not_ready = 0
            sub_vnets_with_overlaps = 0
            sub_subnets_no_workloads = 0
            sub_subnets_public = 0
            sub_subnets_nat_gateway = 0
            sub_subnets_udr = 0
            
            # Calculate per-subscription metrics
            for vnet_id, vnet_data in sub_data['vnets'].items():
                sub_subnets += len(vnet_data['subnets'])
                
                # Count affected subnets manually
                vnet_affected_count = 0
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    if subnet_data['classification'].startswith('Affected'):
                        vnet_affected_count += 1
                sub_affected_subnets += vnet_affected_count
                
                # VNet classification counts
                vnet_classification = vnet_data.get('classification', 'Not Affected')
                if vnet_classification == 'Affected':
                    sub_vnets_not_ready += 1  # Affected VNets need attention
                elif vnet_classification == 'Not Affected':
                    sub_vnets_ready_secure += 1  # Not affected VNets are ready
                else:
                    sub_vnets_not_ready += 1  # Default to needing attention
                
                if vnet_data.get('overlapping_cidrs', []):
                    sub_vnets_with_overlaps += 1
                
                # Count by subnet classification and reason
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    classification = subnet_data['classification']
                    reason = subnet_data.get('reason', '')
                    
                    if classification == 'Not Affected':
                        sub_not_affected += 1
                        if reason == 'No Workloads':
                            sub_subnets_no_workloads += 1
                        elif reason == 'Public Subnet':
                            sub_subnets_public += 1
                        elif reason == 'Azure NAT Gateway':
                            sub_subnets_nat_gateway += 1
                        elif 'UDR with 0.0.0.0/0' in reason:
                            sub_subnets_udr += 1
                    elif classification == 'Affected: Default Egress':
                        sub_default_egress += 1
                    elif classification == 'Affected: Mixed-Mode':
                        sub_mixed_mode += 1
            
            # Add to totals
            total_vnets += sub_vnets
            total_subnets += sub_subnets
            total_affected_subnets += sub_affected_subnets
            total_default_egress += sub_default_egress
            total_mixed_mode += sub_mixed_mode
            total_not_affected += sub_not_affected
            total_vnets_ready_secure += sub_vnets_ready_secure
            total_vnets_ready_insecure += sub_vnets_ready_insecure
            total_vnets_not_ready += sub_vnets_not_ready
            total_vnets_with_overlaps += sub_vnets_with_overlaps
            total_subnets_no_workloads += sub_subnets_no_workloads
            total_subnets_public += sub_subnets_public
            total_subnets_nat_gateway += sub_subnets_nat_gateway
            total_subnets_udr += sub_subnets_udr
            
            # Print subscription summary
            print(f"\n{Colors.BOLD}Subscription: {sub_data['display_name']} ({sub_id}){Colors.ENDC}")
            print(f"  VNets: {sub_vnets} (Ready Secure: {sub_vnets_ready_secure}, Ready Insecure: {sub_vnets_ready_insecure}, Not Ready: {sub_vnets_not_ready})")
            print(f"  Subnets: {sub_subnets}")
            print(f"  Affected Subnets: {sub_affected_subnets}")
            print(f"  VNets with Overlapping CIDRs: {sub_vnets_with_overlaps}")
            print(f"  Subnet Classification:")
            print(f"    {Colors.GREEN}Not Affected: {sub_not_affected} (No Workloads: {sub_subnets_no_workloads}, Public: {sub_subnets_public}, NAT Gateway: {sub_subnets_nat_gateway}, UDR: {sub_subnets_udr}){Colors.ENDC}")
            print(f"    {Colors.YELLOW}Default Egress: {sub_default_egress}{Colors.ENDC}")
            print(f"    {Colors.RED}Mixed-Mode: {sub_mixed_mode}{Colors.ENDC}")
        
        # Print overall summary
        print(f"\n{Colors.HEADER}==================== OVERALL SUMMARY ===================={Colors.ENDC}")
        print(f"Total Subscriptions: {len(self.assessment_data)}")
        print(f"Total VNets: {total_vnets}")
        print(f"  Ready (Secure): {total_vnets_ready_secure}")
        print(f"  Ready (Insecure): {total_vnets_ready_insecure}")
        print(f"  Not Ready: {total_vnets_not_ready}")
        print(f"Total Subnets: {total_subnets}")
        print(f"Total Affected Subnets: {total_affected_subnets}")
        print(f"Total VNets with Overlapping CIDRs: {total_vnets_with_overlaps}")
        print(f"Subnet Classification:")
        print(f"  {Colors.GREEN}Not Affected: {total_not_affected}{Colors.ENDC}")
        print(f"    - No Workloads: {total_subnets_no_workloads}")
        print(f"    - Public Subnets: {total_subnets_public}")
        print(f"    - NAT Gateway: {total_subnets_nat_gateway}")
        print(f"    - UDR with 0.0.0.0/0: {total_subnets_udr}")
        print(f"  {Colors.YELLOW}Default Egress: {total_default_egress}{Colors.ENDC}")
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
        total_workloads = 0
        total_workloads_public_ip = 0
        
        # VNet classification counters
        vnets_ready_secure = 0
        vnets_ready_insecure = 0
        vnets_not_ready = 0
        
        # Subnet classification counters
        subnets_not_affected_no_workloads = 0
        subnets_not_affected_public_subnet = 0
        subnets_not_affected_nat_gateway = 0
        subnets_not_affected_udr = 0
        subnets_affected_default_egress = 0
        subnets_affected_mixed_mode = 0
        
        # Egress mechanism counters
        nat_gateway_count = 0
        udr_count = 0
        default_egress_count = 0
        public_subnet_count = 0
        
        for sub_id, sub_data in self.assessment_data.items():
            sub_vnets = len(sub_data['vnets'])
            total_vnets += sub_vnets
            
            for vnet_id, vnet_data in sub_data['vnets'].items():
                # VNet classification
                vnet_classification = vnet_data.get('classification', 'Not Affected')
                if vnet_classification == 'Affected':
                    vnets_not_ready += 1  # Affected VNets need attention
                elif vnet_classification == 'Not Affected':
                    vnets_ready_secure += 1  # Not affected VNets are ready
                else:
                    vnets_not_ready += 1  # Default to needing attention
                
                vnet_subnets = len(vnet_data['subnets'])
                total_subnets += vnet_subnets
                
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    # Workload counting - use NICs as workloads
                    total_workloads += subnet_data.get('nic_count', 0)
                    total_workloads_public_ip += subnet_data.get('public_ip_count', 0)
                    
                    # Subnet classification
                    classification = subnet_data['classification']
                    reason = subnet_data.get('reason', '')
                    
                    if classification == 'Not Affected':
                        if 'No Workloads' in reason:
                            subnets_not_affected_no_workloads += 1
                        elif 'Public Subnet' in reason:
                            subnets_not_affected_public_subnet += 1
                            public_subnet_count += 1
                        elif 'Azure NAT Gateway' in reason:
                            subnets_not_affected_nat_gateway += 1
                            nat_gateway_count += 1
                        elif 'UDR with 0.0.0.0/0' in reason:
                            subnets_not_affected_udr += 1
                            udr_count += 1
                    elif classification == 'Affected: Default Egress':
                        subnets_affected_default_egress += 1
                        default_egress_count += 1
                    elif classification == 'Affected: Mixed-Mode':
                        subnets_affected_mixed_mode += 1
        
        # Calculate totals for affected subnets
        total_affected_subnets = subnets_affected_default_egress + subnets_affected_mixed_mode
        total_not_affected_subnets = (subnets_not_affected_no_workloads + 
                                    subnets_not_affected_public_subnet + 
                                    subnets_not_affected_nat_gateway + 
                                    subnets_not_affected_udr)
        
        # Calculate percentages
        impact_percentage = 0
        if total_subnets > 0:
            impact_percentage = round((total_affected_subnets / total_subnets) * 100, 1)
        
        workloads_public_ip_percentage = 0
        if total_workloads > 0:
            workloads_public_ip_percentage = round((total_workloads_public_ip / total_workloads) * 100, 1)
        
        # Calculate workloads at risk (those in affected subnets)
        workloads_with_default_egress = 0
        workloads_with_public_ips = total_workloads_public_ip
        
        for sub_id, sub_data in self.assessment_data.items():
            for vnet_id, vnet_data in sub_data['vnets'].items():
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    classification = subnet_data['classification']
                    if classification in ['Affected: Default Egress', 'Affected: Mixed-Mode']:
                        workloads_with_default_egress += subnet_data.get('nic_count', 0)
        
        # Calculate VNETs needing remediation (Ready: Insecure + Not Ready)
        vnets_needing_remediation = vnets_ready_insecure + vnets_not_ready
        
        # Calculate workload-weighted subnet classification
        workloads_no_workloads = 0
        workloads_public_subnet = 0
        workloads_nat_gateway = 0
        workloads_udr = 0
        workloads_default_egress = 0
        workloads_mixed_mode = 0
        
        for sub_id, sub_data in self.assessment_data.items():
            for vnet_id, vnet_data in sub_data['vnets'].items():
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    workload_count = subnet_data.get('nic_count', 0)
                    classification = subnet_data['classification']
                    reason = subnet_data.get('reason', '')
                    
                    if classification == 'Not Affected':
                        if 'No Workloads' in reason:
                            workloads_no_workloads += workload_count
                        elif 'Public Subnet' in reason:
                            workloads_public_subnet += workload_count
                        elif 'Azure NAT Gateway' in reason:
                            workloads_nat_gateway += workload_count
                        elif 'UDR with 0.0.0.0/0' in reason:
                            workloads_udr += workload_count
                    elif classification == 'Affected: Default Egress':
                        workloads_default_egress += workload_count
                    elif classification == 'Affected: Mixed-Mode':
                        workloads_mixed_mode += workload_count
        
        # Calculate VNet percentages
        vnets_ready_secure_percentage = 0
        vnets_ready_insecure_percentage = 0
        vnets_not_ready_percentage = 0
        vnets_needing_remediation_percentage = 0
        
        if total_vnets > 0:
            vnets_ready_secure_percentage = round((vnets_ready_secure / total_vnets) * 100, 1)
            vnets_ready_insecure_percentage = round((vnets_ready_insecure / total_vnets) * 100, 1)
            vnets_not_ready_percentage = round((vnets_not_ready / total_vnets) * 100, 1)
            vnets_needing_remediation_percentage = round((vnets_needing_remediation / total_vnets) * 100, 1)
        
        # Calculate subnet percentages
        subnets_affected_percentage = 0
        subnets_affected_default_egress_percentage = 0
        subnets_affected_mixed_mode_percentage = 0
        
        if total_subnets > 0:
            subnets_affected_percentage = round((total_affected_subnets / total_subnets) * 100, 1)
            subnets_affected_default_egress_percentage = round((subnets_affected_default_egress / total_subnets) * 100, 1)
            subnets_affected_mixed_mode_percentage = round((subnets_affected_mixed_mode / total_subnets) * 100, 1)
        
        # Get CIDR overlap data
        cidr_overlaps = getattr(self, 'cidr_overlaps', [])
        cidr_overlap_count = len(cidr_overlaps)
        
        # Generate table rows and content
        vnet_details_rows = self._generate_vnet_details_rows()
        subnet_details_rows = self._generate_subnet_details_rows()
        subscription_summary_rows = self._generate_subscription_summary_rows()
        subscription_details = self._generate_subscription_details()
        
        # Prepare template data
        template_data = {
            'generated_date': self.start_time.strftime('%B %d, %Y at %I:%M %p'),
            'last_updated': self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'subscriptions_count': len(self.assessment_data),
            
            # Executive Summary metrics
            'total_vnets': total_vnets,
            'total_subnets': total_subnets,
            'total_workloads': total_workloads,
            'total_workloads_public_ip': total_workloads_public_ip,
            'workloads_public_ip_percentage': workloads_public_ip_percentage,
            'workloads_with_default_egress': workloads_with_default_egress,
            'workloads_with_public_ips': workloads_with_public_ips,
            'impact_percentage': impact_percentage,
            'total_affected_subnets': total_affected_subnets,
            'total_not_affected_subnets': total_not_affected_subnets,
            'cidr_overlap_count': cidr_overlap_count,
            'vnets_needing_remediation': vnets_needing_remediation,
            
            # VNet classification
            'vnets_ready_secure': vnets_ready_secure,
            'vnets_ready_insecure': vnets_ready_insecure,
            'vnets_not_ready': vnets_not_ready,
            'vnets_ready_secure_percentage': vnets_ready_secure_percentage,
            'vnets_ready_insecure_percentage': vnets_ready_insecure_percentage,
            'vnets_not_ready_percentage': vnets_not_ready_percentage,
            'vnets_needing_remediation_percentage': vnets_needing_remediation_percentage,
            
            # Subnet classification with reasons
            'subnets_not_affected_no_workloads': subnets_not_affected_no_workloads,
            'subnets_not_affected_public_subnet': subnets_not_affected_public_subnet,
            'subnets_not_affected_nat_gateway': subnets_not_affected_nat_gateway,
            'subnets_not_affected_udr': subnets_not_affected_udr,
            'subnets_affected': total_affected_subnets,
            'subnets_affected_percentage': subnets_affected_percentage,
            'subnets_affected_default_egress': subnets_affected_default_egress,
            'subnets_affected_default_egress_percentage': subnets_affected_default_egress_percentage,
            'subnets_affected_mixed_mode': subnets_affected_mixed_mode,
            'subnets_affected_mixed_mode_percentage': subnets_affected_mixed_mode_percentage,
            
            # Additional chart variables
            'subnets_not_affected': total_not_affected_subnets,
            'subnets_default_egress': subnets_affected_default_egress,
            'subnets_mixed_mode': subnets_affected_mixed_mode,
            'subnets_no_workloads': subnets_not_affected_no_workloads,
            'subnets_public': subnets_not_affected_public_subnet,
            'subnets_nat_gateway': subnets_not_affected_nat_gateway,
            'subnets_udr': subnets_not_affected_udr,
            'egress_none': subnets_not_affected_no_workloads,  # No workloads means no egress needed
            'egress_nat_gateway': nat_gateway_count,
            'egress_udr': udr_count,
            'egress_default': default_egress_count,
            
            # Workload-weighted subnet classification data
            'workloads_no_workloads': workloads_no_workloads,
            'workloads_public_subnet': workloads_public_subnet,
            'workloads_nat_gateway': workloads_nat_gateway,
            'workloads_udr': workloads_udr,
            'workloads_default_egress_chart': workloads_default_egress,
            'workloads_mixed_mode': workloads_mixed_mode,
            
            # Egress mechanisms
            'nat_gateway_count': nat_gateway_count,
            'udr_count': udr_count,
            'default_egress_count': default_egress_count,
            'public_subnet_count': public_subnet_count,
            
            # Table content
            'vnet_details_rows': vnet_details_rows,
            'subnet_details_rows': subnet_details_rows,
            'subscription_summary_rows': subscription_summary_rows,
            'subscription_details': subscription_details,
            
            # CIDR overlaps
            'cidr_overlaps': cidr_overlaps
        };
        
        return template_data
    
    def _generate_subnet_details_rows(self):
        """Generate HTML table rows for Subnet details in Impact Assessment"""
        rows = []
        
        for sub_id, sub_data in self.assessment_data.items():
            for vnet_id, vnet_data in sub_data['vnets'].items():
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    classification = subnet_data['classification']
                    reason = subnet_data.get('reason', '')
                    
                    # Determine classification styling and remediation
                    if classification == 'Not Affected':
                        classification_class = 'status-not-affected'
                        remediation = 'No action needed'
                    elif classification == 'Affected: Default Egress':
                        classification_class = 'status-affected-default'
                        remediation = 'Implement NAT Gateway or UDR with controlled egress'
                    elif classification == 'Affected: Mixed-Mode':
                        classification_class = 'status-affected-mixed'
                        remediation = 'Review mixed-mode configuration and standardize egress method'
                    else:
                        classification_class = 'status-unknown'
                        remediation = 'Review configuration'
                    
                    # Get egress mechanism
                    egress_mechanism = subnet_data.get('egress_mechanism', 'Unknown')
                    
                    # Get workload counts
                    nic_count = subnet_data.get('nic_count', 0)
                    public_ip_count = subnet_data.get('public_ip_count', 0)
                    
                    row = f"""
                    <tr>
                        <td>{sub_data['display_name']}</td>
                        <td>{vnet_data['name']}</td>
                        <td>{subnet_data['name']}</td>
                        <td>{subnet_data['address_prefix']}</td>
                        <td><span class="status-badge {classification_class}">{classification}</span></td>
                        <td>{reason}</td>
                        <td>{egress_mechanism}</td>
                        <td>{nic_count}</td>
                        <td>{public_ip_count}</td>
                        <td>{remediation}</td>
                    </tr>"""
                    rows.append(row)
        
        return '\n'.join(rows)
    
    def _generate_vnet_details_rows(self):
        """Generate HTML table rows for VNet details in Impact Assessment"""
        rows = []
        
        for sub_id, sub_data in self.assessment_data.items():
            for vnet_id, vnet_data in sub_data['vnets'].items():
                # Recalculate VNet classification based on subnet classifications
                has_affected_subnets = False
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    if subnet_data['classification'].startswith('Affected'):
                        has_affected_subnets = True
                        break
                
                # Set simple classification
                if has_affected_subnets:
                    classification = 'Affected'
                else:
                    classification = 'Not Affected'
                
                # Determine classification styling
                if classification == 'Affected':
                    classification_class = 'status-affected'
                elif classification == 'Not Affected':
                    classification_class = 'status-not-affected'
                else:
                    classification_class = 'status-unknown'
                
                # Collect egress mechanisms used across all subnets in this VNet
                egress_mechanisms = set()
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    # Check the stored egress mechanism first
                    mechanism = subnet_data.get('egress_mechanism', '')
                    reason = subnet_data.get('reason', '')
                    subnet_classification = subnet_data.get('classification', '')
                    
                    # Map based on reason and classification
                    if 'Azure NAT Gateway' in reason:
                        egress_mechanisms.add('NAT Gateway')
                    elif 'UDR with 0.0.0.0/0' in reason:
                        egress_mechanisms.add('UDR')
                    elif 'Public Subnet' in reason:
                        egress_mechanisms.add('Public Subnet')
                    elif 'Using default egress' in reason:
                        egress_mechanisms.add('Default Egress')
                    elif 'Mixed mode' in reason:
                        egress_mechanisms.add('Mixed Mode')
                    elif 'No Workloads' in reason:
                        egress_mechanisms.add('No Workloads')
                    elif mechanism and mechanism != 'Unknown':
                        egress_mechanisms.add(mechanism)
                    else:
                        # Fallback based on classification
                        if 'Not Affected' in subnet_classification:
                            egress_mechanisms.add('Secured')
                        elif 'Affected' in subnet_classification:
                            egress_mechanisms.add('Default/Mixed')
                
                egress_mechanisms_str = ', '.join(sorted(egress_mechanisms)) if egress_mechanisms else 'None'
                
                # Count subnets by classification and workloads
                affected_subnets = 0
                not_affected_subnets = 0
                total_workloads = 0
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    total_workloads += subnet_data.get('nic_count', 0)
                    if subnet_data['classification'].startswith('Affected'):
                        affected_subnets += 1
                    else:
                        not_affected_subnets += 1
                
                row = f"""
                <tr>
                    <td>{sub_data['display_name']}</td>
                    <td>{vnet_data['name']}</td>
                    <td><span class="status-badge {classification_class}">{classification}</span></td>
                    <td>{', '.join(vnet_data['address_space'])}</td>
                    <td>{len(vnet_data['subnets'])}</td>
                    <td>{total_workloads}</td>
                    <td>{egress_mechanisms_str}</td>
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
            subnets_total = 0
            subnets_affected = 0
            workloads_total = 0
            workloads_public_ip = 0
            
            for vnet_id, vnet_data in sub_data['vnets'].items():
                vnet_has_affected_subnets = False
                
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    subnets_total += 1
                    workloads_total += subnet_data.get('nic_count', 0)
                    workloads_public_ip += subnet_data.get('public_ip_count', 0)
                    
                    if subnet_data['classification'].startswith('Affected'):
                        subnets_affected += 1
                        vnet_has_affected_subnets = True
                
                if vnet_has_affected_subnets:
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
                <td>{subnets_total}</td>
                <td>{subnets_affected}</td>
                <td>{workloads_total}</td>
                <td>{workloads_public_ip}</td>
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
                
                # Count affected subnets
                affected_count = 0
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    if subnet_data['classification'].startswith('Affected'):
                        affected_count += 1
                
                # Get VNet classification and capabilities
                vnet_classification = vnet_data.get('classification', 'Not Affected')
                
                # Determine VNet classification CSS class
                if vnet_classification == 'Affected':
                    vnet_class = 'status-affected'
                elif vnet_classification == 'Not Affected':
                    vnet_class = 'status-not-affected'
                else:
                    vnet_class = 'status-unknown'
                    
                capabilities = []
                if vnet_data.get('has_nat_gateway', False):
                    capabilities.append('NAT Gateway')
                if vnet_data.get('has_udr', False):
                    capabilities.append('UDR')
                capabilities_str = ', '.join(capabilities) if capabilities else 'None'
                
                detail_section += f"""
                <div class="vnet-detail">
                    <h4>{vnet_name}</h4>
                    <p><strong>Resource Group:</strong> {resource_group}</p>
                    <p><strong>Address Space:</strong> {address_space}</p>
                    <p><strong>Classification:</strong> <span class="status-badge {vnet_class}">{vnet_classification}</span></p>
                    <p><strong>Capabilities:</strong> {capabilities_str}</p>
                    <p><strong>Subnets:</strong> {subnets_count} total, {affected_count} affected</p>"""
                
                if subnets_count > 0:
                    detail_section += """
                    <h5>Subnets</h5>
                    <ul>"""
                    
                    # Add subnet details
                    for subnet_id, subnet_data in vnet_data['subnets'].items():
                        subnet_name = subnet_data['name']
                        classification = subnet_data['classification']
                        reason = subnet_data.get('reason', '')
                        address_prefix = subnet_data['address_prefix']
                        
                        if classification == 'Not Affected':
                            classification_class = 'status-not-affected'
                        elif classification == 'Affected: Default Egress':
                            classification_class = 'status-affected-default'
                        elif classification == 'Affected: Mixed-Mode':
                            classification_class = 'status-affected-mixed'
                        else:
                            classification_class = 'status-unknown'
                        
                        # Add route next hop information for UDR subnets
                        route_info = ""
                        if 'UDR with 0.0.0.0/0' in reason:
                            next_hop = subnet_data.get('default_route_next_hop', '')
                            next_hop_ip = subnet_data.get('default_route_next_hop_ip', '')
                            if next_hop:
                                route_info = f" (Next Hop: {next_hop}"
                                if next_hop_ip:
                                    route_info += f" -> {next_hop_ip}"
                                route_info += ")"
                        
                        detail_section += f"""
                        <li>{subnet_name} ({address_prefix}): <span class="status-badge {classification_class}">{classification}</span>
                            {f' - {reason}{route_info}' if reason else ''}
                        </li>"""
                    
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
            # Calculate summary statistics with new classification system
            total_vnets = 0
            total_subnets = 0
            total_affected_subnets = 0
            total_default_egress = 0
            total_mixed_mode = 0
            total_not_affected = 0
            
            for sub_id, sub_data in self.assessment_data.items():
                sub_vnets = len(sub_data['vnets'])
                total_vnets += sub_vnets
                
                for vnet_id, vnet_data in sub_data['vnets'].items():
                    vnet_subnets = len(vnet_data['subnets'])
                    total_subnets += vnet_subnets
                    
                    for subnet_id, subnet_data in vnet_data['subnets'].items():
                        classification = subnet_data['classification']
                        if classification == 'Not Affected':
                            total_not_affected += 1
                        elif classification == 'Affected: Default Egress':
                            total_default_egress += 1
                            total_affected_subnets += 1
                        elif classification == 'Affected: Mixed-Mode':
                            total_mixed_mode += 1
                            total_affected_subnets += 1
            
            # Generate HTML content using the existing method
            html_content = self._generate_html_content(
                total_vnets, total_subnets, total_affected_subnets,
                total_default_egress, total_mixed_mode, total_not_affected
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
                              total_default_egress, total_mixed_mode, total_not_affected):
        """Generate the actual HTML content for the report"""
        
        # Generate current date/time
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate percentages for charts
        affected_percent = 0
        if total_subnets > 0:
            affected_percent = (total_affected_subnets / total_subnets) * 100
        
        default_egress_percent = 0
        mixed_mode_percent = 0
        not_affected_percent = 0
        if total_subnets > 0:
            default_egress_percent = (total_default_egress / total_subnets) * 100
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
                    elif classification == 'Affected: Default Egress':
                        risk_level = 'High'
                        remediation = 'Implement controlled egress (NAT Gateway or UDR)'
                        classification_class = 'affected-default'
                    elif classification == 'Affected: Mixed-Mode':
                        risk_level = 'Critical'
                        remediation = 'Review and standardize mixed-mode configuration'
                        classification_class = 'affected-mixed'
                    else:
                        risk_level = 'Unknown'
                        remediation = 'Review configuration'
                        classification_class = 'unknown'
                    
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
                # Count affected subnets manually
                affected_count = 0
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    if subnet_data['classification'].startswith('Affected'):
                        affected_count += 1
                
                if affected_count > 0:
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
            <p><strong>For Default Egress Subnets:</strong> Add a route table with a default route (0.0.0.0/0) pointing to an NVA or deploy a NAT Gateway for controlled egress.</p>
            <p><strong>For Mixed-Mode Subnets:</strong> Consider restructuring the subnet to separate resources with public IPs from those without, or implement a consistent connectivity strategy.</p>
            <p><strong>General Recommendation:</strong> Standardize egress methods across your environment for better security and management.</p>
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
                
                # Count affected subnets manually
                affected_count = 0
                for subnet_id, subnet_data in vnet_data['subnets'].items():
                    if subnet_data['classification'].startswith('Affected'):
                        affected_count += 1
                
                html += f"""
            <div class="vnet">
                <h3>VNet: {vnet_name}</h3>
                <p><strong>Resource Group:</strong> {resource_group}</p>
                <p><strong>Address Space:</strong> {address_space}</p>
                <p><strong>Subnets:</strong> {subnets_count} total, {affected_count} affected</p>
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
                        elif classification == "Affected: Default Egress":
                            classification_class = "affected-default"
                        elif classification == "Affected: Mixed-Mode":
                            classification_class = "affected-mixed"
                        else:
                            classification_class = "unknown"
                        
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
                    labels: ['Not Affected', 'Default Egress', 'Mixed-Mode'],
                    datasets: [{
                        data: [""" + f"{total_not_affected}, {total_default_egress}, {total_mixed_mode}" + """],
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
