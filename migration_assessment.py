#!/usr/bin/env python3
"""
MuleSoft Migration Assessment Tool

This tool analyzes MuleSoft codebases to assess migration complexity and feasibility of a migration.
It extracts key metrics without exposing actual source code, making it safe for clients to share
the generated reports.

Usage:
    python migration_assessment.py <path_to_repositories_folder>

Author: Juan Heyns <juan.heyns@epiuse.com>
(c) copyright 2025, EPI-USE America, Inc. All rights reserved.
"""

import sys
import json
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from datetime import datetime
from collections import Counter
import argparse


class MuleSoftAnalyzer:
    def __init__(self):
        self.analysis_results = {
            'metadata': {
                'analysis_date': datetime.now().isoformat(),
                'analyzer_version': '1.0.0'
            },
            'summary': {
                'total_projects': 0,
                'mule_4_projects': 0,
                'mule_3_projects': 0,
                'unknown_version_projects': 0
            },
            'projects': []
        }
        
        # Common Mule connectors and their complexity scores
        self.connector_complexity_scores = {
            'http': 1,
            'db': 2,
            'file': 1,
            'ftp': 2,
            'sftp': 2,
            'jms': 3,
            'vm': 1,
            'sap': 5,
            'salesforce': 4,
            'servicenow': 4,
            'aws-s3': 3,
            'aws-sqs': 3,
            'email': 2,
            'compression': 1,
            'crypto': 2,
            'validation': 1,
            'json': 1,
            'xml': 2,
            'apikit': 2,
            'oauth': 3,
            'spring': 2,
            'scripting': 3,
            'java': 4
        }
    
    def analyze_repository_folder(self, repo_folder_path, target_projects=None):
        """Analyze a folder containing multiple MuleSoft repositories"""
        repo_folder = Path(repo_folder_path)
        self.target_projects = target_projects
        
        if not repo_folder.exists():
            raise FileNotFoundError(f"Repository folder not found: {repo_folder_path}")
        
        if target_projects:
            print(f"Analyzing specific projects in {repo_folder}: {', '.join(target_projects)}")
        else:
            print(f"Analyzing repositories in: {repo_folder}")
        
        # Find all potential MuleSoft projects with hierarchical structure support
        self._find_mulesoft_projects_recursive(repo_folder, repo_folder)
        
        # Update summary statistics
        self._calculate_summary_stats()
        return self.analysis_results
    
    def _find_mulesoft_projects_recursive(self, current_path, base_path, max_depth=4):
        """Recursively find MuleSoft projects in hierarchical directory structure"""
        current_depth = len(current_path.relative_to(base_path).parts)
        
        # Don't go too deep to avoid infinite recursion
        if current_depth > max_depth:
            return
        
        for item in current_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if this directory is a MuleSoft project
                if self._is_mulesoft_project(item):
                    # Filter by specific projects if specified
                    if hasattr(self, 'target_projects') and self.target_projects:
                        if item.name not in self.target_projects:
                            continue
                    
                    # Calculate relative path for better project identification
                    relative_path = item.relative_to(base_path)
                    project_display_name = str(relative_path) if len(relative_path.parts) > 1 else item.name
                    
                    print(f"Analyzing project: {project_display_name}")
                    project_analysis = self.analyze_project(item)
                    
                    # Update project name to include path context for hierarchical structure
                    if len(relative_path.parts) > 1:
                        project_analysis['project_display_name'] = project_display_name
                        project_analysis['project_source'] = '/'.join(relative_path.parts[:-1])
                    else:
                        project_analysis['project_display_name'] = item.name
                        project_analysis['project_source'] = 'local'
                    
                    self.analysis_results['projects'].append(project_analysis)
                    self.analysis_results['summary']['total_projects'] += 1
                else:
                    # Recurse into subdirectories to find projects
                    self._find_mulesoft_projects_recursive(item, base_path, max_depth)
    
    def _is_mulesoft_project(self, project_path):
        """Check if a directory is a MuleSoft project"""
        indicators = [
            project_path / 'pom.xml',
            project_path / 'mule-artifact.json',
            project_path / 'src' / 'main' / 'mule'
        ]
        return any(indicator.exists() for indicator in indicators)
    
    def analyze_project(self, project_path):
        """Analyze a single MuleSoft project"""
        project_analysis = {
            'project_name': project_path.name,
            'project_path': str(project_path),
            'mule_version': 'unknown',
            'is_legacy': False,
            'configuration_files': {
                'count': 0,
                'files': []
            },
            'flows_and_subflows': {
                'total_flows': 0,
                'total_subflows': 0,
                'flows_per_file': {},
                'complex_flows': []  # Flows with >50 components
            },
            'connectors_and_components': {
                'unique_connectors': [],
                'connector_usage_count': {},
                'component_types': {},  # Detailed breakdown by component type
                'total_components': 0,
                'complexity_score': 0
            },
            'dataweave_analysis': {
                'dwl_files_count': 0,
                'inline_dw_expressions_count': 0,
                'complex_transformations': 0,  # >100 lines
                'total_dw_lines': 0
            },
            'custom_code': {
                'java_files_count': 0,
                'java_classes': [],
                'groovy_scripts_count': 0,
                'total_custom_code_lines': 0
            },
            'testing': {
                'munit_test_files': 0,
                'munit_test_cases': 0,
                'other_test_files': 0
            },
            'shared_resources': {
                'domain_projects': 0,
                'shared_libraries': [],
                'common_configurations': []
            },
            'complexity_indicators': {
                'large_files': [],  # >1000 lines
                'deeply_nested_flows': [],
                'error_handling_patterns': 0,
                'async_patterns': 0
            }
        }
        
        # Analyze different aspects of the project
        self._analyze_mule_version(project_path, project_analysis)
        self._analyze_configuration_files(project_path, project_analysis)
        self._analyze_custom_code(project_path, project_analysis)
        self._analyze_tests(project_path, project_analysis)
        self._analyze_shared_resources(project_path, project_analysis)
        self._calculate_project_complexity(project_analysis)
        
        return project_analysis
    
    def _analyze_mule_version(self, project_path, analysis):
        """Extract Mule runtime version from pom.xml"""
        pom_path = project_path / 'pom.xml'
        if pom_path.exists():
            try:
                tree = ET.parse(pom_path)
                root = tree.getroot()
                
                # Define namespace
                ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
                
                # Look for mule.version property
                for prop in root.findall('.//maven:properties', ns):
                    mule_version = prop.find('maven:mule.version', ns)
                    if mule_version is not None:
                        analysis['mule_version'] = mule_version.text
                        analysis['is_legacy'] = mule_version.text.startswith('3.')
                        break
                
                # Also check for mule-maven-plugin version as fallback
                if analysis['mule_version'] == 'unknown':
                    for plugin in root.findall('.//maven:plugin', ns):
                        artifact_id = plugin.find('maven:artifactId', ns)
                        if artifact_id is not None and artifact_id.text == 'mule-maven-plugin':
                            version = plugin.find('maven:version', ns)
                            if version is not None:
                                analysis['mule_version'] = f"plugin-{version.text}"
                                break
                            
            except ET.ParseError as e:
                print(f"Warning: Could not parse pom.xml in {project_path.name}: {e}")
    
    def _analyze_configuration_files(self, project_path, analysis):
        """Analyze Mule configuration XML files"""
        mule_config_path = project_path / 'src' / 'main' / 'mule'
        
        if mule_config_path.exists():
            xml_files = list(mule_config_path.glob('**/*.xml'))
            analysis['configuration_files']['count'] = len(xml_files)
            
            for xml_file in xml_files:
                file_analysis = self._analyze_xml_file(xml_file)
                analysis['configuration_files']['files'].append({
                    'filename': xml_file.name,
                    'relative_path': str(xml_file.relative_to(project_path)),
                    'size_lines': file_analysis['line_count'],
                    'flows': file_analysis['flows'],
                    'subflows': file_analysis['subflows'],
                    'components': file_analysis['components'],
                    'xml_tags_by_namespace': file_analysis['xml_tags_by_namespace']
                })
                
                # Aggregate flow and component statistics
                analysis['flows_and_subflows']['total_flows'] += file_analysis['flows']
                analysis['flows_and_subflows']['total_subflows'] += file_analysis['subflows']
                analysis['flows_and_subflows']['flows_per_file'][xml_file.name] = file_analysis['flows']
                analysis['connectors_and_components']['total_components'] += file_analysis['components']
                
                # Track large files
                if file_analysis['line_count'] > 1000:
                    analysis['complexity_indicators']['large_files'].append({
                        'filename': xml_file.name,
                        'lines': file_analysis['line_count']
                    })
                
                # Analyze connectors used in this file
                self._extract_connectors_from_xml(xml_file, analysis)
                
                # Analyze DataWeave in this file
                self._analyze_dataweave_in_xml(xml_file, analysis)
    
    def _analyze_xml_file(self, xml_file_path):
        """Analyze a single XML configuration file"""
        analysis = {
            'line_count': 0,
            'flows': 0,
            'subflows': 0,
            'components': 0,
            'xml_tags_by_namespace': {}
        }
        
        try:
            with open(xml_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                analysis['line_count'] = len(content.splitlines())
            
            # Parse XML to count flows and components
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            
            # Extract namespace mappings from schema locations and xmlns declarations
            namespace_mappings = {}
            
            # Parse schema locations
            schema_locations = root.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation', '')
            if schema_locations:
                parts = schema_locations.split()
                for i in range(0, len(parts), 2):
                    if i + 1 < len(parts):
                        namespace_uri = parts[i]
                        if 'mulesoft.org/schema/mule' in namespace_uri:
                            connector_name = namespace_uri.split('/')[-1]
                            # Find the prefix for this namespace
                            for attr_name, attr_value in root.attrib.items():
                                if attr_value == namespace_uri and attr_name.startswith('xmlns:'):
                                    prefix = attr_name.split(':')[1]
                                    namespace_mappings[namespace_uri] = {
                                        'prefix': prefix,
                                        'connector_name': connector_name
                                    }
                                    break
            
            # Also parse direct namespace declarations
            for key, value in root.attrib.items():
                if key.startswith('xmlns:') and 'mulesoft.org/schema/mule' in value:
                    prefix = key.split(':')[1]
                    connector_name = value.split('/')[-1]
                    namespace_mappings[value] = {
                        'prefix': prefix,
                        'connector_name': connector_name
                    }
            
            # Count elements by namespace and local name
            xml_tags_by_namespace = {}
            
            for element in root.iter():
                # Extract namespace and local name from element tag
                if '}' in element.tag:
                    # Format: {namespace}localname
                    namespace_uri, local_name = element.tag.rsplit('}', 1)
                    namespace_uri = namespace_uri[1:]  # Remove leading '{'
                    
                    # Map namespace URI to connector name
                    if namespace_uri in namespace_mappings:
                        connector_info = namespace_mappings[namespace_uri]
                        namespace_key = f"{connector_info['connector_name']} ({connector_info['prefix']}:)"
                    elif 'mulesoft.org/schema/mule' in namespace_uri:
                        connector_name = namespace_uri.split('/')[-1]
                        namespace_key = f"{connector_name} (ns:)"
                    else:
                        namespace_key = f"other ({namespace_uri})"
                else:
                    # No namespace or default namespace
                    local_name = element.tag
                    namespace_key = "default"
                
                if namespace_key not in xml_tags_by_namespace:
                    xml_tags_by_namespace[namespace_key] = {}
                
                xml_tags_by_namespace[namespace_key][local_name] = \
                    xml_tags_by_namespace[namespace_key].get(local_name, 0) + 1
            
            analysis['xml_tags_by_namespace'] = xml_tags_by_namespace
            
            # Count flows and subflows (using namespace-aware search)
            flows_count = 0
            subflows_count = 0
            for element in root.iter():
                if element.tag.endswith('}flow') or element.tag == 'flow':
                    flows_count += 1
                elif element.tag.endswith('}sub-flow') or element.tag == 'sub-flow':
                    subflows_count += 1
            
            analysis['flows'] = flows_count
            analysis['subflows'] = subflows_count
            
            # Count all XML elements as potential components
            analysis['components'] = len(list(root.iter())) - 1  # Subtract root element
            
        except (ET.ParseError, UnicodeDecodeError) as e:
            print(f"Warning: Could not parse XML file {xml_file_path}: {e}")
        
        return analysis
    
    def _extract_connectors_from_xml(self, xml_file_path, analysis):
        """Extract connector usage from XML namespaces and elements"""
        try:
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            
            # Extract namespaces to identify connectors from schema locations
            namespaces = {}
            schema_locations = root.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation', '')
            if schema_locations:
                parts = schema_locations.split()
                for i in range(0, len(parts), 2):
                    if i + 1 < len(parts):
                        namespace_uri = parts[i]
                        if 'mulesoft.org/schema/mule' in namespace_uri:
                            connector_name = namespace_uri.split('/')[-1]
                            if connector_name not in ['core', 'documentation']:
                                # Find the prefix for this namespace
                                for attr_name, attr_value in root.attrib.items():
                                    if attr_value == namespace_uri and attr_name.startswith('xmlns:'):
                                        prefix = attr_name.split(':')[1]
                                        namespaces[prefix] = connector_name
                                        break
            
            # Also parse direct namespace declarations
            for key, value in root.attrib.items():
                if key.startswith('xmlns:') and 'mulesoft.org/schema/mule' in value:
                    prefix = key.split(':')[1]
                    connector_name = value.split('/')[-1]
                    if connector_name not in ['core', 'documentation']:
                        namespaces[prefix] = connector_name
            
            # Count usage of each connector and component type
            for element in root.iter():
                # Extract namespace prefix from element tag
                if '}' in element.tag:
                    # Format: {namespace}localname
                    namespace_uri, local_name = element.tag.rsplit('}', 1)
                    namespace_uri = namespace_uri[1:]  # Remove leading '{'
                    
                    # Map namespace URI to connector name
                    connector_name = None
                    if 'mulesoft.org/schema/mule' in namespace_uri:
                        connector_name = namespace_uri.split('/')[-1]
                        if connector_name in ['core', 'documentation']:
                            connector_name = 'core'
                elif ':' in element.tag:
                    # Format: prefix:localname
                    prefix, local_name = element.tag.split(':', 1)
                    connector_name = namespaces.get(prefix)
                else:
                    # No namespace prefix
                    local_name = element.tag
                    connector_name = 'core'
                
                if connector_name:
                    # Count connector usage
                    analysis['connectors_and_components']['connector_usage_count'][connector_name] = \
                        analysis['connectors_and_components']['connector_usage_count'].get(connector_name, 0) + 1
                    
                    # Count component types
                    component_type = f"{connector_name}:{local_name}" if connector_name != 'core' else local_name
                    analysis['connectors_and_components']['component_types'][component_type] = \
                        analysis['connectors_and_components']['component_types'].get(component_type, 0) + 1
            
            # Update unique connectors list
            unique_connectors = set(analysis['connectors_and_components']['unique_connectors'])
            unique_connectors.update(namespaces.values())
            analysis['connectors_and_components']['unique_connectors'] = list(unique_connectors)
            
        except (ET.ParseError, UnicodeDecodeError) as e:
            print(f"Warning: Could not extract connectors from {xml_file_path}: {e}")
    
    def _analyze_dataweave_in_xml(self, xml_file_path, analysis):
        """Analyze DataWeave expressions in XML files"""
        try:
            with open(xml_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find inline DataWeave expressions
            dw_patterns = [
                r'#\[.*?\]',  # Simple #[...] expressions
                r'<!\[CDATA\[#\[.*?\]\]\]>',  # CDATA wrapped expressions
                r'output\s+application/\w+.*?---.*?(?=\]\]>|\])',  # DataWeave transformations
            ]
            
            total_inline_dw = 0
            complex_transformations = 0
            total_dw_lines = 0
            
            for pattern in dw_patterns:
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                total_inline_dw += len(matches)
                
                for match in matches:
                    lines = match.count('\n') + 1
                    total_dw_lines += lines
                    if lines > 10:  # Consider >10 lines as complex
                        complex_transformations += 1
            
            analysis['dataweave_analysis']['inline_dw_expressions_count'] += total_inline_dw
            analysis['dataweave_analysis']['complex_transformations'] += complex_transformations
            analysis['dataweave_analysis']['total_dw_lines'] += total_dw_lines
            
        except UnicodeDecodeError as e:
            print(f"Warning: Could not read XML file for DataWeave analysis {xml_file_path}: {e}")
    
    def _analyze_custom_code(self, project_path, analysis):
        """Analyze custom Java code and other scripts"""
        java_path = project_path / 'src' / 'main' / 'java'
        
        if java_path.exists():
            java_files = list(java_path.glob('**/*.java'))
            analysis['custom_code']['java_files_count'] = len(java_files)
            
            total_lines = 0
            for java_file in java_files:
                try:
                    with open(java_file, 'r', encoding='utf-8') as f:
                        lines = len(f.readlines())
                        total_lines += lines
                    
                    # Extract class name from file
                    class_name = java_file.stem
                    analysis['custom_code']['java_classes'].append({
                        'class_name': class_name,
                        'file_path': str(java_file.relative_to(project_path)),
                        'lines': lines
                    })
                except UnicodeDecodeError:
                    print(f"Warning: Could not read Java file {java_file}")
            
            analysis['custom_code']['total_custom_code_lines'] = total_lines
        
        # Look for DataWeave files
        resources_path = project_path / 'src' / 'main' / 'resources'
        if resources_path.exists():
            dwl_files = list(resources_path.glob('**/*.dwl'))
            analysis['dataweave_analysis']['dwl_files_count'] = len(dwl_files)
            
            for dwl_file in dwl_files:
                try:
                    with open(dwl_file, 'r', encoding='utf-8') as f:
                        lines = len(f.readlines())
                        analysis['dataweave_analysis']['total_dw_lines'] += lines
                        if lines > 100:
                            analysis['dataweave_analysis']['complex_transformations'] += 1
                except UnicodeDecodeError:
                    print(f"Warning: Could not read DataWeave file {dwl_file}")
    
    def _analyze_tests(self, project_path, analysis):
        """Analyze MUnit and other test files"""
        munit_path = project_path / 'src' / 'test' / 'munit'
        
        if munit_path.exists():
            munit_files = list(munit_path.glob('**/*.xml'))
            analysis['testing']['munit_test_files'] = len(munit_files)
            
            # Count test cases in MUnit files
            total_test_cases = 0
            for munit_file in munit_files:
                try:
                    tree = ET.parse(munit_file)
                    root = tree.getroot()
                    
                    # Count munit:test elements
                    test_cases = len(root.findall('.//{http://www.mulesoft.org/schema/mule/munit}test'))
                    total_test_cases += test_cases
                    
                except (ET.ParseError, UnicodeDecodeError):
                    print(f"Warning: Could not parse MUnit file {munit_file}")
            
            analysis['testing']['munit_test_cases'] = total_test_cases
        
        # Look for other test files
        test_path = project_path / 'src' / 'test'
        if test_path.exists():
            other_test_files = []
            for pattern in ['**/*.java', '**/*.groovy', '**/*.py']:
                other_test_files.extend(test_path.glob(pattern))
            analysis['testing']['other_test_files'] = len(other_test_files)
    
    def _analyze_shared_resources(self, project_path, analysis):
        """Analyze shared resources and libraries"""
        # Check for domain projects (typically have domain in the name or specific structure)
        if 'domain' in project_path.name.lower():
            analysis['shared_resources']['domain_projects'] = 1
        
        # Look for common configuration patterns (exclude catalog files)
        config_files = []
        resources_path = project_path / 'src' / 'main' / 'resources'
        if resources_path.exists():
            config_patterns = ['*.properties', '*.yaml', '*.yml', '*.json']
            for pattern in config_patterns:
                files = resources_path.glob(f'**/{pattern}')
                # Filter out catalog files (check both filename and path)
                filtered_files = [f for f in files if 'catalog' not in str(f).lower()]
                config_files.extend(filtered_files)
        
        analysis['shared_resources']['common_configurations'] = [
            {
                'filename': f.name,
                'type': f.suffix,
                'path': str(f.relative_to(project_path))
            }
            for f in config_files
        ]
    
    def _calculate_project_complexity(self, analysis):
        """Calculate overall project complexity score"""
        complexity_score = 0
        
        # Base complexity from connectors
        for connector, count in analysis['connectors_and_components']['connector_usage_count'].items():
            base_score = self.connector_complexity_scores.get(connector, 2)
            complexity_score += base_score * count
        
        # Add complexity for flows and components
        complexity_score += analysis['flows_and_subflows']['total_flows'] * 2
        complexity_score += analysis['flows_and_subflows']['total_subflows'] * 1
        complexity_score += analysis['connectors_and_components']['total_components'] * 0.1
        
        # Add complexity for custom code
        complexity_score += analysis['custom_code']['java_files_count'] * 5
        complexity_score += analysis['custom_code']['total_custom_code_lines'] * 0.01
        
        # Add complexity for DataWeave
        complexity_score += analysis['dataweave_analysis']['dwl_files_count'] * 3
        complexity_score += analysis['dataweave_analysis']['complex_transformations'] * 5
        
        # Large files penalty
        complexity_score += len(analysis['complexity_indicators']['large_files']) * 10
        
        analysis['connectors_and_components']['complexity_score'] = round(complexity_score, 2)
    
    def _calculate_summary_stats(self):
        """Calculate summary statistics across all projects"""
        mule_4_count = 0
        mule_3_count = 0
        unknown_count = 0
        
        for project in self.analysis_results['projects']:
            version = project['mule_version']
            if version.startswith('4.'):
                mule_4_count += 1
            elif version.startswith('3.'):
                mule_3_count += 1
            else:
                unknown_count += 1
        
        self.analysis_results['summary']['mule_4_projects'] = mule_4_count
        self.analysis_results['summary']['mule_3_projects'] = mule_3_count
        self.analysis_results['summary']['unknown_version_projects'] = unknown_count
        
        # Calculate totals across all projects
        totals = {
            'total_flows': sum(p['flows_and_subflows']['total_flows'] for p in self.analysis_results['projects']),
            'total_subflows': sum(p['flows_and_subflows']['total_subflows'] for p in self.analysis_results['projects']),
            'total_components': sum(p['connectors_and_components']['total_components'] for p in self.analysis_results['projects']),
            'total_java_files': sum(p['custom_code']['java_files_count'] for p in self.analysis_results['projects']),
            'total_dwl_files': sum(p['dataweave_analysis']['dwl_files_count'] for p in self.analysis_results['projects']),
            'total_munit_tests': sum(p['testing']['munit_test_files'] for p in self.analysis_results['projects']),
            'total_complexity_score': sum(p['connectors_and_components']['complexity_score'] for p in self.analysis_results['projects'])
        }
        
        self.analysis_results['summary'].update(totals)
        
        # Aggregate connector usage across all projects
        all_connectors = Counter()
        all_component_types = Counter()
        for project in self.analysis_results['projects']:
            for connector, count in project['connectors_and_components']['connector_usage_count'].items():
                all_connectors[connector] += count
            for component_type, count in project['connectors_and_components']['component_types'].items():
                all_component_types[component_type] += count
        
        self.analysis_results['summary']['connector_usage_summary'] = dict(all_connectors)
        self.analysis_results['summary']['component_types_summary'] = dict(all_component_types)
    
    def generate_report(self, output_file, individual_files=False, output_dir='report'):
        """Generate a comprehensive analysis report"""
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        print(f"Generating analysis report in: {output_dir}/")
        
        # Generate main summary report in the output directory
        main_json_file = output_path / "mulesoft_analysis_analysis.json"
        
        if individual_files:
            # When using individual files, just include summary and project list
            summary_results = {
                'metadata': self.analysis_results['metadata'],
                'summary': self.analysis_results['summary'],
                'project_list': [
                    {
                        'project_name': p['project_name'],
                        'project_display_name': p.get('project_display_name', p['project_name']),
                        'project_source': p.get('project_source', 'local'),
                        'mule_version': p['mule_version'],
                        'is_legacy': p['is_legacy'],
                        'flows': p['flows_and_subflows']['total_flows'],
                        'components': p['connectors_and_components']['total_components'],
                        'complexity_score': p['connectors_and_components']['complexity_score'],
                        'java_files': p['custom_code']['java_files_count'],
                        'munit_tests': p['testing']['munit_test_files']
                    }
                    for p in self.analysis_results['projects']
                ]
            }
        else:
            # When NOT using individual files, include full project details in consolidated file
            summary_results = {
                'metadata': self.analysis_results['metadata'],
                'summary': self.analysis_results['summary'],
                'projects': []
            }
            
            # Add restructured project data for each project
            for project in self.analysis_results['projects']:
                project_data = {
                    'project_overview': {
                        'project_name': project['project_name'],
                        'project_display_name': project.get('project_display_name', project['project_name']),
                        'project_source': project.get('project_source', 'local'),
                        'project_path': project['project_path'],
                        'mule_version': project['mule_version'],
                        'is_legacy': project['is_legacy']
                    },
                    'configuration_files': project['configuration_files'],
                    'dataweave_analysis': project['dataweave_analysis'],
                    'custom_code': project['custom_code'],
                    'testing': project['testing'],
                    'shared_resources': project['shared_resources'],
                    'complexity_indicators': project['complexity_indicators'],
                    'summary_stats': {
                        'flows_and_subflows': project['flows_and_subflows'],
                        'connectors_and_components': project['connectors_and_components']
                    }
                }
                summary_results['projects'].append(project_data)
        
        with open(main_json_file, 'w', encoding='utf-8') as f:
            json.dump(summary_results, f, indent=2, ensure_ascii=False)
        
        # Generate individual project files if requested
        if individual_files:
            self._generate_individual_project_files(output_dir)
        
        # Always generate the comprehensive overview report
        comprehensive_file = output_path / "mulesoft_analysis_comprehensive.txt"
        self._generate_comprehensive_index(comprehensive_file)
        
        # Generate human-readable summary in the same directory
        summary_file = output_path / "mulesoft_analysis_summary.txt"
        self._generate_human_readable_summary(summary_file)
        
        print(f"MuleSoft Migration Assessment complete! All reports generated in: {output_dir}/")
        if individual_files:
            print(f"  - JSON Summary: {main_json_file}")
            print(f"  - Individual project files: {len(self.analysis_results['projects'])} JSON files")
        else:
            print(f"  - Consolidated Analysis: {main_json_file} (includes all project details)")
        print(f"  - Comprehensive Overview: {comprehensive_file}")
        print(f"  - Summary Report: {summary_file}")
        
        print(f"\nReady for sharing: zip the '{output_dir}' folder and email to stakeholders.")
    
    def _generate_individual_project_files(self, output_dir):
        """Generate individual JSON files for each project"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        print(f"Generating individual project files in: {output_path}")
        
        for project in self.analysis_results['projects']:
            project_file = output_path / f"{project['project_name']}_analysis.json"
            
            # Create a restructured project report with requested structure
            project_report = {
                'metadata': self.analysis_results['metadata'],
                'project_overview': {
                    'project_name': project['project_name'],
                    'project_display_name': project.get('project_display_name', project['project_name']),
                    'project_source': project.get('project_source', 'local'),
                    'project_path': project['project_path'],
                    'mule_version': project['mule_version'],
                    'is_legacy': project['is_legacy']
                },
                'configuration_files': project['configuration_files'],
                'dataweave_analysis': project['dataweave_analysis'],
                'custom_code': project['custom_code'],
                'testing': project['testing'],
                'shared_resources': project['shared_resources'],
                'complexity_indicators': project['complexity_indicators'],
                # Keep summary stats for reference
                'summary_stats': {
                    'flows_and_subflows': project['flows_and_subflows'],
                    'connectors_and_components': project['connectors_and_components']
                }
            }
            
            with open(project_file, 'w', encoding='utf-8') as f:
                json.dump(project_report, f, indent=2, ensure_ascii=False)
        
        # Create comprehensive index/overview file
        index_file = output_path / "mulesoft_analysis_comprehensive.txt"
        self._generate_comprehensive_index(index_file)
    
    def _generate_comprehensive_index(self, index_file):
        """Generate a comprehensive index file with SUMMARY and aggregated analysis"""

        with open(index_file, 'w', encoding='utf-8') as f:
            f.write("MULESOFT MIGRATION ASSESSMENT - COMPREHENSIVE\n")
            f.write("=" * 45 + "\n\n")
            
            # SUMMARY
            f.write("SUMMARY\n")
            f.write("-" * 17 + "\n")
            f.write(f"Analysis Date: {self.analysis_results['metadata']['analysis_date']}\n")
            f.write(f"Analyzer Version: {self.analysis_results['metadata']['analyzer_version']}\n")
            f.write(f"Total Projects Analyzed: {len(self.analysis_results['projects'])}\n\n")
            
            # Version Distribution
            mule_4_count = sum(1 for p in self.analysis_results['projects'] if p['mule_version'].startswith('4.'))
            mule_3_count = sum(1 for p in self.analysis_results['projects'] if p['mule_version'].startswith('3.'))
            unknown_count = len(self.analysis_results['projects']) - mule_4_count - mule_3_count
            
            f.write("MULE VERSION DISTRIBUTION\n")
            f.write("-" * 25 + "\n")
            f.write(f"Mule 4.x Projects: {mule_4_count}\n")
            f.write(f"Mule 3.x Projects (Legacy): {mule_3_count}\n")
            f.write(f"Unknown/Other Versions: {unknown_count}\n\n")
            
            if mule_3_count > 0:
                f.write(f"⚠️  CRITICAL: {mule_3_count} Mule 3.x projects require full migration!\n\n")
            
            # Overall Statistics
            total_flows = sum(p['flows_and_subflows']['total_flows'] for p in self.analysis_results['projects'])
            total_subflows = sum(p['flows_and_subflows']['total_subflows'] for p in self.analysis_results['projects'])
            total_components = sum(p['connectors_and_components']['total_components'] for p in self.analysis_results['projects'])
            total_java_files = sum(p['custom_code']['java_files_count'] for p in self.analysis_results['projects'])
            total_dwl_files = sum(p['dataweave_analysis']['dwl_files_count'] for p in self.analysis_results['projects'])
            total_munit_tests = sum(p['testing']['munit_test_files'] for p in self.analysis_results['projects'])
            total_complexity = sum(p['connectors_and_components']['complexity_score'] for p in self.analysis_results['projects'])
            
            f.write("CODEBASE STATISTICS\n")
            f.write("-" * 19 + "\n")
            f.write(f"Total Flows: {total_flows:,}\n")
            f.write(f"Total Subflows: {total_subflows:,}\n")
            f.write(f"Total Components: {total_components:,}\n")
            f.write(f"Custom Java Files: {total_java_files:,}\n")
            f.write(f"DataWeave Files: {total_dwl_files:,}\n")
            f.write(f"MUnit Test Files: {total_munit_tests:,}\n")
            f.write(f"Average Complexity per Project: {total_complexity/len(self.analysis_results['projects']):.1f}\n\n")
            
            # XML Tags Analysis Across All Projects
            f.write("XML TAGS USAGE ACROSS ALL PROJECTS\n")
            f.write("-" * 34 + "\n")
            
            # Aggregate all XML tags from all projects
            all_tags = {}
            all_namespace_tags = {}
            
            for project in self.analysis_results['projects']:
                for config_file in project['configuration_files']['files']:
                    for namespace, tags in config_file.get('xml_tags_by_namespace', {}).items():
                        if namespace not in all_namespace_tags:
                            all_namespace_tags[namespace] = {}
                        for tag, count in tags.items():
                            all_tags[tag] = all_tags.get(tag, 0) + count
                            all_namespace_tags[namespace][tag] = all_namespace_tags[namespace].get(tag, 0) + count
            
            # Sort tags by usage count, excluding core and mule:ee namespace tags
            connector_tags = {}
            excluded_tags = {}
            
            for project in self.analysis_results['projects']:
                for config_file in project['configuration_files']['files']:
                    for namespace, tags in config_file.get('xml_tags_by_namespace', {}).items():
                        for tag, count in tags.items():
                            # Exclude core and mule:ee namespaces
                            if 'core' in namespace.lower() or 'ee' in namespace.lower():
                                excluded_tags[tag] = excluded_tags.get(tag, 0) + count
                            else:
                                # Extract namespace prefix for display
                                # Format examples: "db (ns:)", "http (ns:)", "api-gateway (ns:)"
                                if '(' in namespace:
                                    # Get the part before the parentheses
                                    prefix = namespace.split('(')[0].strip()
                                else:
                                    prefix = namespace.split(' ')[0]
                                
                                # Create namespaced tag name
                                namespaced_tag = f"{prefix}:{tag}" if prefix != 'default' else tag
                                connector_tags[namespaced_tag] = connector_tags.get(namespaced_tag, 0) + count
            
            sorted_connector_tags = sorted(connector_tags.items(), key=lambda x: x[1], reverse=True)
            
            f.write("Used XML Tags (excluding core and mule:ee namespaces):\n")
            for i, (namespaced_tag, count) in enumerate(sorted_connector_tags, 1):
                f.write(f"{i:2d}. {namespaced_tag:<30} {count:>6,} usages\n")
            
            f.write(f"\nCore/EE namespace tags (excluded above): {sum(excluded_tags.values()):,} total usages\n")
            
            f.write(f"\nTotal Unique XML Tags Found: {len(all_tags)}\n\n")
            
            # Tags by Namespace
            f.write("\nXML TAGS BY NAMESPACE\n")
            f.write("-" * 21 + "\n")
            
            for namespace in sorted(all_namespace_tags.keys()):
                namespace_total = sum(all_namespace_tags[namespace].values())
                f.write(f"\n{namespace} ({namespace_total:,} total usages):\n")
                
                # Sort tags within this namespace
                sorted_namespace_tags = sorted(all_namespace_tags[namespace].items(), 
                                             key=lambda x: x[1], reverse=True)
                
                # Show all tags for this namespace
                for tag, count in sorted_namespace_tags:
                    f.write(f"  {tag:<20} {count:>6,}\n")
            
            # Get high complexity projects for recommendations
            high_complexity = [p for p in self.analysis_results['projects'] if p['connectors_and_components']['complexity_score'] > 1000]
            
            # Large Files Analysis
            large_files_count = sum(len(p['complexity_indicators']['large_files']) for p in self.analysis_results['projects'])
            if large_files_count > 0:
                f.write("\nLARGE FILES (>1000 lines)\n")
                f.write("-" * 25 + "\n")
                f.write(f"Total Large Configuration Files: {large_files_count}\n")
                
                # List all large files across projects
                all_large_files = []
                for project in self.analysis_results['projects']:
                    for large_file in project['complexity_indicators']['large_files']:
                        all_large_files.append({
                            'project': project['project_name'],
                            'filename': large_file['filename'],
                            'lines': large_file['lines']
                        })
                
                # Sort by size
                all_large_files.sort(key=lambda x: x['lines'], reverse=True)
                
                f.write("Largest files:\n")
                for file_info in all_large_files[:10]:  # Show top 10
                    f.write(f"  {file_info['project']}/{file_info['filename']}: {file_info['lines']:,} lines\n")
                f.write("\n")
            
            # Custom Code Analysis
            if total_java_files > 0:
                f.write("CUSTOM CODE ANALYSIS\n")
                f.write("-" * 20 + "\n")
                
                total_java_lines = sum(p['custom_code']['total_custom_code_lines'] for p in self.analysis_results['projects'])
                projects_with_java = sum(1 for p in self.analysis_results['projects'] if p['custom_code']['java_files_count'] > 0)
                
                f.write(f"Projects with Custom Java Code: {projects_with_java}\n")
                f.write(f"Total Java Files: {total_java_files:,}\n")
                f.write(f"Total Java Lines of Code: {total_java_lines:,}\n")
                f.write(f"Average Java Lines per Project: {total_java_lines/projects_with_java:.0f}\n\n")
            
            # DataWeave Analysis
            if total_dwl_files > 0 or any(p['dataweave_analysis']['inline_dw_expressions_count'] > 0 for p in self.analysis_results['projects']):
                f.write("DATAWEAVE ANALYSIS\n")
                f.write("-" * 18 + "\n")
                
                total_inline_dw = sum(p['dataweave_analysis']['inline_dw_expressions_count'] for p in self.analysis_results['projects'])
                total_complex_dw = sum(p['dataweave_analysis']['complex_transformations'] for p in self.analysis_results['projects'])
                total_dw_lines = sum(p['dataweave_analysis']['total_dw_lines'] for p in self.analysis_results['projects'])
                
                f.write(f"DataWeave (.dwl) Files: {total_dwl_files:,}\n")
                f.write(f"Inline DataWeave Expressions: {total_inline_dw:,}\n")
                f.write(f"Complex Transformations: {total_complex_dw:,}\n")
                f.write(f"Total DataWeave Lines of Code: {total_dw_lines:,}\n\n")
            
            # Project Files List
            f.write("INDIVIDUAL PROJECT FILES\n")
            f.write("-" * 24 + "\n")
            
            # Sort projects by complexity score (descending)
            sorted_projects = sorted(self.analysis_results['projects'], 
                                   key=lambda x: x['connectors_and_components']['complexity_score'], 
                                   reverse=True)
            
            for project in sorted_projects:
                complexity_score = project['connectors_and_components']['complexity_score']
                risk_level = "HIGH" if complexity_score > 1000 else "MEDIUM" if complexity_score > 500 else "LOW"
                flows = project['flows_and_subflows']['total_flows']
                components = project['connectors_and_components']['total_components']
                java_files = project['custom_code']['java_files_count']
                
                # Use display name if available, otherwise use project name
                display_name = project.get('project_display_name', project['project_name'])
                source_info = project.get('project_source', '')
                
                f.write(f"- {project['project_name']}_analysis.json\n")
                if source_info and source_info != 'local':
                    f.write(f"   Source: {source_info}\n")
                f.write(f"   Path: {display_name}\n")
                f.write(f"   Mule: {project['mule_version']:<8} Risk: {risk_level:<6} Complexity: {complexity_score:>7.0f}\n")
                f.write(f"   Flows: {flows:<4} Components: {components:<6} Java Files: {java_files}\n")
                f.write("\n")
            
            f.write("RECOMMENDATIONS\n")
            f.write("-" * 15 + "\n")
            
            if mule_3_count > 0:
                f.write("CRITICAL PRIORITY:\n")
                f.write(f"- {mule_3_count} Mule 3.x projects require complete rewrite (end-of-life)\n\n")
            
            if len(high_complexity) > 0:
                f.write("HIGH PRIORITY:\n")
                f.write(f"- {len(high_complexity)} projects have high complexity (>1000)\n")
                f.write("- Consider phased migration approach for these projects\n\n")
            
            if total_java_files > 0:
                f.write("MEDIUM PRIORITY:\n")
                f.write(f"- {total_java_files} Java files need review and potential rewriting\n")
                f.write("- Assess if custom logic can be replaced with standard connectors\n\n")
            
            if large_files_count > 0:
                f.write("OPTIMIZATION OPPORTUNITIES:\n")
                f.write(f"- {large_files_count} large configuration files may benefit from refactoring\n")
                f.write("- Consider breaking monolithic flows into smaller, manageable pieces\n\n")
            
    def _generate_human_readable_summary(self, output_file):
        """Generate a human-readable summary report"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("MULESOFT MIGRATION ASSESSMENT - SUMMARY\n")
            f.write("=" * 39 + "\n\n")
            
            summary = self.analysis_results['summary']
            
            f.write("SUMMARY\n")
            f.write("-" * 7 + "\n")
            f.write(f"Analysis Date: {self.analysis_results['metadata']['analysis_date']}\n")
            f.write(f"Total Projects Analyzed: {summary['total_projects']}\n")
            f.write(f"Mule 4.x Projects: {summary['mule_4_projects']}\n")
            f.write(f"Mule 3.x Projects (Legacy): {summary['mule_3_projects']}\n")
            f.write(f"Unknown Version Projects: {summary['unknown_version_projects']}\n\n")
            
            if summary['mule_3_projects'] > 0:
                f.write(f"⚠️  WARNING: Mule 3.x projects found! These require full migration as Mule 3 reached end-of-life in 2021.\n\n")
            
            f.write("CODEBASE STATISTICS\n")
            f.write("-" * 19 + "\n")
            f.write(f"Total Flows: {summary.get('total_flows', 0)}\n")
            f.write(f"Total Subflows: {summary.get('total_subflows', 0)}\n")
            f.write(f"Total Components: {summary.get('total_components', 0)}\n")
            f.write(f"Custom Java Files: {summary.get('total_java_files', 0)}\n")
            f.write(f"DataWeave Files: {summary.get('total_dwl_files', 0)}\n")
            f.write(f"MUnit Test Files: {summary.get('total_munit_tests', 0)}\n")
            f.write(f"Overall Complexity Score: {summary.get('total_complexity_score', 0):.2f}\n\n")
            
            f.write("CONNECTOR USAGE SUMMARY\n")
            f.write("-" * 23 + "\n")
            connector_summary = summary.get('connector_usage_summary', {})
            for connector, count in sorted(connector_summary.items(), key=lambda x: x[1], reverse=True):
                complexity = self.connector_complexity_scores.get(connector, 2)
                risk_level = "HIGH" if complexity >= 4 else "MEDIUM" if complexity >= 3 else "LOW"
                f.write(f"{connector}: {count} usages (Migration Risk: {risk_level})\n")
            
            f.write("\nTOP COMPONENT TYPES (by usage)\n")
            f.write("-" * 29 + "\n")
            component_types_summary = summary.get('component_types_summary', {})
            # Show top 15 most used component types
            top_components = sorted(component_types_summary.items(), key=lambda x: x[1], reverse=True)[:15]
            for component_type, count in top_components:
                f.write(f"{component_type}: {count} usages\n")
            
            f.write("\nPROJECT BREAKDOWN\n")
            f.write("-" * 17 + "\n")
            for project in self.analysis_results['projects']:
                display_name = project.get('project_display_name', project['project_name'])
                source_info = project.get('project_source', '')
                
                f.write(f"\nProject: {display_name}\n")
                if source_info and source_info != 'local':
                    f.write(f"  Source: {source_info}\n")
                f.write(f"  Mule Version: {project['mule_version']}\n")
                f.write(f"  Flows: {project['flows_and_subflows']['total_flows']}\n")
                f.write(f"  Components: {project['connectors_and_components']['total_components']}\n")
                f.write(f"  Complexity Score: {project['connectors_and_components']['complexity_score']:.1f}\n")
                f.write(f"  Custom Code: {project['custom_code']['java_files_count']} Java files\n")
                f.write(f"  Tests: {project['testing']['munit_test_files']} MUnit files\n")
                
                if project['complexity_indicators']['large_files']:
                    f.write(f"  ⚠️  Large files: {len(project['complexity_indicators']['large_files'])}\n")
                    
                # Show top component types for this project
                component_types = project['connectors_and_components']['component_types']
                if component_types:
                    top_3_components = sorted(component_types.items(), key=lambda x: x[1], reverse=True)[:3]
                    f.write(f"  Top components: {', '.join([f'{comp}({count})' for comp, count in top_3_components])}\n")
            

def main():
    parser = argparse.ArgumentParser(description='MuleSoft Migration Assessment Tool - Analyze MuleSoft codebases for migration planning')
    parser.add_argument('repo_folder', help='Path to folder containing MuleSoft repositories')
    parser.add_argument('-o', '--output', default='mulesoft_analysis_output.json', 
                       help='Output file name (ignored - all files go to output-dir)')
    parser.add_argument('--projects', nargs='*', 
                       help='Specific project names to analyze (default: analyze all projects)')
    parser.add_argument('--individual-files', action='store_true',
                       help='Generate individual JSON files for each project (default: consolidated single file)')
    parser.add_argument('--output-dir', default='report_output',
                       help='Output directory for analysis files (default: report_output)')
    
    args = parser.parse_args()
    
    try:
        analyzer = MuleSoftAnalyzer()
        analyzer.analyze_repository_folder(args.repo_folder, args.projects)
        analyzer.generate_report(args.output, args.individual_files, args.output_dir)
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()