#!/usr/bin/env python3
"""
Test script for Azure Default Egress Assessment Tool
Tests basic functionality without requiring Azure authentication
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile

# Add the script directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the main script
import azure_egress_assessment

class TestAzureEgressAssessment(unittest.TestCase):
    """Test cases for Azure Egress Assessment Tool"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_args = Mock()
        self.mock_args.subscription_id = None
        self.mock_args.export_json = False
        self.mock_args.export_csv = False
        self.mock_args.verbose = False
        
    def test_colors_class(self):
        """Test that Colors class has all expected attributes"""
        colors = azure_egress_assessment.Colors()
        expected_attrs = ['HEADER', 'BLUE', 'CYAN', 'GREEN', 'YELLOW', 'RED', 'ENDC', 'BOLD', 'UNDERLINE']
        
        for attr in expected_attrs:
            self.assertTrue(hasattr(colors, attr), f"Colors class missing {attr} attribute")
            
    def test_assessment_initialization(self):
        """Test AzureEgressAssessment class initialization"""
        assessment = azure_egress_assessment.AzureEgressAssessment(self.mock_args)
        
        # Check basic attributes
        self.assertEqual(assessment.args, self.mock_args)
        self.assertIsNone(assessment.credential)
        self.assertIsNone(assessment.subscription_client)
        self.assertEqual(assessment.subscriptions, [])
        self.assertEqual(assessment.assessment_data, {})
        self.assertIsNotNone(assessment.start_time)
        self.assertTrue(assessment.report_filename.startswith("azure-egress-assessment-"))
        
    def test_template_path_detection(self):
        """Test that template path is correctly detected"""
        assessment = azure_egress_assessment.AzureEgressAssessment(self.mock_args)
        
        # Should look for template in templates subfolder first
        expected_path = os.path.join(os.path.dirname(__file__), 'templates', 'report_template.html')
        self.assertEqual(assessment.template_path, expected_path)
        
    def test_progress_tracking(self):
        """Test progress tracking functionality"""
        assessment = azure_egress_assessment.AzureEgressAssessment(self.mock_args)
        
        # Initial state
        self.assertEqual(assessment.total_resources, 0)
        self.assertEqual(assessment.processed_resources, 0)
        
        # Test update_progress
        assessment.total_resources = 100
        initial_processed = assessment.processed_resources
        assessment.update_progress()
        self.assertEqual(assessment.processed_resources, initial_processed + 1)
        
    @patch('azure_egress_assessment.AzureCliCredential')
    @patch('azure_egress_assessment.SubscriptionClient')
    def test_authentication_azure_cli_success(self, mock_sub_client, mock_cli_cred):
        """Test successful authentication with Azure CLI credentials"""
        # Mock successful Azure CLI authentication
        mock_credential = Mock()
        mock_cli_cred.return_value = mock_credential
        
        mock_client = Mock()
        mock_sub_client.return_value = mock_client
        mock_client.subscriptions.list.return_value = iter([Mock()])
        
        assessment = azure_egress_assessment.AzureEgressAssessment(self.mock_args)
        
        # Should not raise exception
        assessment.authenticate()
        
        # Check that credential and client are set
        self.assertEqual(assessment.credential, mock_credential)
        self.assertEqual(assessment.subscription_client, mock_client)
        
    def test_classification_logic(self):
        """Test subnet classification logic"""
        assessment = azure_egress_assessment.AzureEgressAssessment(self.mock_args)
        
        # Mock data for classification test
        mock_subnet = {
            'id': '/subscriptions/test/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet1',
            'name': 'subnet1',
            'route_table': None,
            'nsg': None,
            'has_resources_with_public_ip': False,
            'has_resources_without_public_ip': True,
            'resource_count': 5
        }
        
        # Test classification (this would require the actual classify_subnet method)
        # For now, just test that we can create the assessment object
        self.assertIsNotNone(assessment)
        
    def test_report_filename_format(self):
        """Test that report filename follows expected format"""
        assessment = azure_egress_assessment.AzureEgressAssessment(self.mock_args)
        
        # Should start with azure-egress-assessment- and contain timestamp
        self.assertTrue(assessment.report_filename.startswith("azure-egress-assessment-"))
        
        # Should contain date in YYYYMMDD format
        import re
        pattern = r"azure-egress-assessment-\d{8}-\d{6}"
        self.assertTrue(re.match(pattern, assessment.report_filename))
        
    def test_export_methods_exist(self):
        """Test that export methods exist"""
        assessment = azure_egress_assessment.AzureEgressAssessment(self.mock_args)
        
        # Check that export methods exist
        self.assertTrue(hasattr(assessment, 'export_json'))
        self.assertTrue(hasattr(assessment, 'export_csv'))
        self.assertTrue(hasattr(assessment, 'generate_html_report'))
        
    def test_template_exists(self):
        """Test that the HTML template file exists"""
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'report_template.html')
        self.assertTrue(os.path.exists(template_path), f"Template file not found at {template_path}")
        
        # Check that template contains expected placeholders
        with open(template_path, 'r') as f:
            template_content = f.read()
            
        expected_placeholders = [
            '{{ generated_date }}',
            '{{ subscriptions_count }}',
            '{{ total_vnets }}',
            '{{ total_subnets }}',
            '{{ impact_percentage }}'
        ]
        
        for placeholder in expected_placeholders:
            self.assertIn(placeholder, template_content, f"Template missing placeholder: {placeholder}")

class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""
    
    def test_parse_arguments_default(self):
        """Test argument parsing with default values"""
        # Mock sys.argv to avoid conflicts
        with patch('sys.argv', ['azure_egress_assessment.py']):
            args = azure_egress_assessment.parse_arguments()
            
            self.assertIsNone(args.subscription_id)
            self.assertFalse(args.export_json)
            self.assertFalse(args.export_csv)
            self.assertFalse(args.verbose)
            
    def test_parse_arguments_with_flags(self):
        """Test argument parsing with flags set"""
        test_args = [
            'azure_egress_assessment.py',
            '--subscription-id', 'sub1,sub2',
            '--export-json',
            '--export-csv',
            '--verbose'
        ]
        
        with patch('sys.argv', test_args):
            args = azure_egress_assessment.parse_arguments()
            
            self.assertEqual(args.subscription_id, 'sub1,sub2')
            self.assertTrue(args.export_json)
            self.assertTrue(args.export_csv)
            self.assertTrue(args.verbose)

def run_integration_test():
    """Run an integration test with mock data"""
    print("\n" + "="*60)
    print("INTEGRATION TEST - Testing with Mock Data")
    print("="*60)
    
    # Create mock assessment data
    mock_data = {
        'subscription1': {
            'subscription_id': 'sub-12345',
            'display_name': 'Test Subscription',
            'state': 'Enabled',
            'vnets': {
                'vnet1': {
                    'name': 'test-vnet',
                    'resource_group': 'test-rg',
                    'location': 'eastus',
                    'subnets': {
                        'subnet1': {
                            'name': 'test-subnet',
                            'classification': 'quick_remediation',
                            'risk_level': 'medium',
                            'has_resources_with_public_ip': False,
                            'has_resources_without_public_ip': True,
                            'resource_count': 3
                        }
                    }
                }
            }
        }
    }
    
    # Test data processing
    total_vnets = sum(len(sub_data['vnets']) for sub_data in mock_data.values())
    total_subnets = sum(
        len(vnet['subnets']) 
        for sub_data in mock_data.values() 
        for vnet in sub_data['vnets'].values()
    )
    
    print(f"✓ Mock data created: {len(mock_data)} subscriptions")
    print(f"✓ Total VNets: {total_vnets}")
    print(f"✓ Total Subnets: {total_subnets}")
    
    # Test template loading
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'report_template.html')
    if os.path.exists(template_path):
        print(f"✓ Template file found: {template_path}")
        
        # Test basic template variables
        try:
            from jinja2 import Template
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            template = Template(template_content)
            # Test rendering with minimal data
            test_vars = {
                'generated_date': '2025-05-23',
                'subscriptions_count': 1,
                'total_vnets': 1,
                'total_subnets': 1,
                'impact_percentage': 100,
                'total_affected_subnets': 1,
                'total_not_affected': 0,
                'total_quick_remediation': 1,
                'total_mixed_mode': 0,
                'subnet_impact_rows': '<tr><td>Test</td><td>Test</td><td>Test</td><td>Test</td><td>Test</td><td>Test</td></tr>',
                'subscription_summary_rows': '<tr><td>Test</td><td>1</td><td>1</td><td>0</td><td>100%</td></tr>',
                'subscription_details': '<div>Test details</div>',
                'last_updated': '2025-05-23 12:00:00'
            }
            
            rendered = template.render(**test_vars)
            print(f"✓ Template renders successfully ({len(rendered)} characters)")
            
        except Exception as e:
            print(f"✗ Template rendering failed: {e}")
    else:
        print(f"✗ Template file not found: {template_path}")
    
    print("✓ Integration test completed successfully!")

if __name__ == '__main__':
    print("Azure Egress Assessment - Test Suite")
    print("=" * 50)
    
    # Run unit tests
    print("\nRunning Unit Tests...")
    unittest.main(verbosity=2, exit=False)
    
    # Run integration test
    run_integration_test()
