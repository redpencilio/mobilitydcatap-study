#!/usr/bin/env python3

import requests
from urllib.parse import quote
import json
from collections import defaultdict

class DCATVocabularyChecker:
    def __init__(self, sparql_endpoint="http://host.docker.internal:8890/sparql"):
        self.sparql_endpoint = sparql_endpoint
        self.results = defaultdict(dict)

    def execute_sparql(self, query):
        """Execute SPARQL query against the endpoint"""
        headers = {
            'Accept': 'application/sparql-results+json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {'query': query}

        try:
            response = requests.post(self.sparql_endpoint, headers=headers, data=data)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error executing SPARQL query: {e}")
            return None

    def get_catalog_entities(self):
        """Get all catalogs and their associated entities (datasets, distributions, etc.)"""
        # First get all catalogs
        catalog_query = """
        PREFIX dcat: <http://www.w3.org/ns/dcat#>
        SELECT DISTINCT ?catalog WHERE {
            ?catalog a dcat:Catalog .
        }
        """

        catalog_result = self.execute_sparql(catalog_query)
        if not catalog_result:
            return {}

        catalog_entities = {}

        # For each catalog, get its entities
        for binding in catalog_result.get('results', {}).get('bindings', []):
            catalog = binding['catalog']['value']
            catalog_entities[catalog] = {
                'catalogs': [catalog],
                'datasets': [],
                'distributions': [],
                'records': []
            }

            # Get datasets for this catalog
            dataset_query = f"""
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            SELECT DISTINCT ?dataset ?distribution WHERE {{
                <{catalog}> a dcat:Catalog .
                {{
                    <{catalog}> dcat:dataset ?dataset .
                }} UNION {{
                    <{catalog}> dcat:Dataset ?dataset .
                }}
                ?dataset a dcat:Dataset .
                OPTIONAL {{
                    ?dataset dcat:distribution ?distribution .
                    ?distribution a dcat:Distribution .
                }}
            }}
            """

            dataset_result = self.execute_sparql(dataset_query)
            if dataset_result:
                for ds_binding in dataset_result.get('results', {}).get('bindings', []):
                    dataset = ds_binding['dataset']['value']
                    if dataset not in catalog_entities[catalog]['datasets']:
                        catalog_entities[catalog]['datasets'].append(dataset)

                    if 'distribution' in ds_binding and ds_binding['distribution']:
                        distribution = ds_binding['distribution']['value']
                        if distribution not in catalog_entities[catalog]['distributions']:
                            catalog_entities[catalog]['distributions'].append(distribution)

            # Get catalog records
            record_query = f"""
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            SELECT DISTINCT ?record WHERE {{
                <{catalog}> dcat:record ?record .
                ?record a dcat:CatalogRecord .
            }}
            """

            record_result = self.execute_sparql(record_query)
            if record_result:
                for rec_binding in record_result.get('results', {}).get('bindings', []):
                    record = rec_binding['record']['value']
                    if record not in catalog_entities[catalog]['records']:
                        catalog_entities[catalog]['records'].append(record)

        return catalog_entities

    def check_property_vocabulary(self, property_uri, entity_type, catalog_entities):
        """Check if a property uses controlled vocabulary across catalogs"""
        for catalog, entities in catalog_entities.items():
            entity_list = entities.get(entity_type, [])
            if not entity_list:
                continue

            entity_filter = ' '.join([f"<{entity}>" for entity in entity_list])

            # First get all distinct values and their usage counts
            query = f"""
            PREFIX dcat: <http://www.w3.org/ns/dcat#>

            SELECT DISTINCT ?value (COUNT(?entity) as ?count) WHERE {{
                VALUES ?entity {{ {entity_filter} }}
                ?entity <{property_uri}> ?value .
            }}
            GROUP BY ?value
            ORDER BY DESC(?count)
            """

            # Also count total distinct entities that have this property
            count_query = f"""
            PREFIX dcat: <http://www.w3.org/ns/dcat#>

            SELECT (COUNT(DISTINCT ?entity) as ?total_with_property) WHERE {{
                VALUES ?entity {{ {entity_filter} }}
                ?entity <{property_uri}> ?value .
            }}
            """

            result = self.execute_sparql(query)
            count_result = self.execute_sparql(count_query)
            
            total_entities_with_property = 0
            if count_result and count_result.get('results', {}).get('bindings'):
                total_entities_with_property = int(count_result['results']['bindings'][0]['total_with_property']['value'])

            if result:
                values = []
                for binding in result.get('results', {}).get('bindings', []):
                    value = binding['value']['value']
                    count = int(binding['count']['value'])
                    values.append({'value': value, 'count': count})

                property_key = f"{property_uri} ({entity_type})"
                self.results[catalog][property_key] = {
                    f'total_{entity_type}': len(entity_list),
                    'entities_with_property': total_entities_with_property,
                    'values_found': values,
                    'unique_values': len(values),
                    'has_controlled_vocab': self.analyze_vocabulary_control(values)
                }

    def analyze_vocabulary_control(self, values):
        """Analyze if the values suggest controlled vocabulary usage"""
        if not values:
            return False

        total_usage = sum(v['count'] for v in values)

        if len(values) <= 5:
            return True

        top_values_usage = sum(v['count'] for v in values[:5])
        if top_values_usage / total_usage > 0.8:
            return True

        uri_values = [v for v in values if v['value'].startswith('http')]
        if len(uri_values) / len(values) > 0.7:
            return True

        return False

    def check_properties(self, property_config):
        """Check multiple properties for controlled vocabulary usage"""
        catalog_entities = self.get_catalog_entities()

        if not catalog_entities:
            print("No catalogs or datasets found in the endpoint")
            return

        print(f"Found {len(catalog_entities)} catalogs")

        for prop_uri, entity_type in property_config.items():
            print(f"Checking property: {prop_uri} on {entity_type}")
            self.check_property_vocabulary(prop_uri, entity_type, catalog_entities)

        self.generate_unified_report()

    def generate_unified_report(self):
        """Generate a unified report focused on controlled vocabularies"""
        print("\n" + "="*80)
        print("CONTROLLED VOCABULARY ANALYSIS REPORT")
        print("="*80)

        # Generate org-style table for vocabulary analysis
        self._generate_vocabulary_table()
        
        # Generate extended vocabulary report
        self._generate_extended_vocabulary_report()

    def _show_catalog_compliance_summary(self, catalog):
        """Show compliance summary for a catalog"""
        if catalog not in self.compliance_results:
            print("No compliance data available\n")
            return

        compliance_data = self.compliance_results[catalog]
        print("\nCOMPLIANCE SUMMARY:")

        overall_scores = []
        for class_name, data in compliance_data.items():
            mandatory_total = len(data['mandatory'])
            if mandatory_total > 0:
                mandatory_compliant = sum(1 for info in data['mandatory'].values() if info['compliance_rate'] == 1.0)
                score = mandatory_compliant / mandatory_total
                overall_scores.append(score)

                status = "PASS" if score >= 0.8 else "WARN" if score >= 0.5 else "FAIL"
                print(f"  [{status}] {class_name}: {score:.1%} mandatory compliance ({mandatory_compliant}/{mandatory_total})")

                # Show missing/failed properties
                failed_props = [prop for prop, info in data['mandatory'].items() if info['compliance_rate'] < 1.0]
                if failed_props:
                    print(f"    Missing properties: {', '.join([p.split('#')[-1] if '#' in p else p.split('/')[-1] for p in failed_props])}")
                    for prop in failed_props:
                        info = data['mandatory'][prop]
                        prop_name = prop.split('#')[-1] if '#' in prop else prop.split('/')[-1]
                        print(f"      {prop_name}: {info['present_count']}/{info['total_entities']} entities ({info['compliance_rate']:.1%})")

        if overall_scores:
            avg_score = sum(overall_scores) / len(overall_scores)
            overall_status = "PASS" if avg_score >= 0.8 else "WARN" if avg_score >= 0.5 else "FAIL"
            print(f"  [{overall_status}] Overall Compliance: {avg_score:.1%}")

    def _show_property_analysis(self, catalog):
        """Show detailed property analysis combining vocabulary and compliance info"""
        print("\nPROPERTY ANALYSIS:")

        # Group properties by class
        properties_by_class = {}

        if catalog in self.results:
            for prop_key, vocab_data in self.results[catalog].items():
                # Extract property URI and entity type from key like "uri (entity_type)"
                if " (" in prop_key:
                    prop_uri, entity_type = prop_key.rsplit(" (", 1)
                    entity_type = entity_type.rstrip(")")

                    class_map = {
                        "catalogs": "dcat:Catalog",
                        "datasets": "dcat:Dataset",
                        "distributions": "dcat:Distribution",
                        "records": "dcat:CatalogRecord"
                    }
                    class_name = class_map.get(entity_type, entity_type)

                    if class_name not in properties_by_class:
                        properties_by_class[class_name] = []

                    properties_by_class[class_name].append({
                        'uri': prop_uri,
                        'vocab_data': vocab_data,
                        'entity_type': entity_type
                    })

        # Show properties organized by class
        for class_name in ["dcat:Catalog", "dcat:Dataset", "dcat:Distribution", "dcat:CatalogRecord"]:
            if class_name in properties_by_class:
                print(f"\n  {class_name}:")

                for prop_info in properties_by_class[class_name]:
                    self._show_property_details(catalog, class_name, prop_info)

    def _show_property_details(self, catalog, class_name, prop_info):
        """Show detailed information for a specific property"""
        prop_uri = prop_info['uri']
        vocab_data = prop_info['vocab_data']
        prop_name = prop_uri.split('#')[-1] if '#' in prop_uri else prop_uri.split('/')[-1]

        # Check if property is in mobility spec and get compliance info
        requirement_status = "📄"
        compliance_info = ""
        spec_requirement = self._get_property_requirement(prop_uri, class_name)

        if spec_requirement:
            # Property is in mobility spec
            compliance_data = None
            if catalog in self.compliance_results and class_name in self.compliance_results[catalog]:
                compliance_data = self.compliance_results[catalog][class_name]

            if spec_requirement == "mandatory":
                if compliance_data and prop_uri in compliance_data['mandatory']:
                    compliance_rate = compliance_data['mandatory'][prop_uri]['compliance_rate']
                    requirement_status = "M-FAIL" if compliance_rate < 1.0 else "M-PASS"
                    compliance_info = f" [MANDATORY: {compliance_rate:.1%}]"
                else:
                    requirement_status = "M-FAIL"  # Mandatory but no data = missing
                    compliance_info = " [MANDATORY: 0.0%]"
            elif spec_requirement == "optional":
                if compliance_data and prop_uri in compliance_data['optional']:
                    usage_rate = compliance_data['optional'][prop_uri]['usage_rate']
                    requirement_status = "OPT"
                    compliance_info = f" [OPTIONAL: {usage_rate:.1%}]"
                else:
                    requirement_status = "OPT"
                    compliance_info = " [OPTIONAL: 0.0%]"

        # Enhanced vocabulary status with clearer codelist indication
        vocab_info = self._get_vocabulary_info(vocab_data)

        entity_count_key = [k for k in vocab_data.keys() if k.startswith('total_')][0] if any(k.startswith('total_') for k in vocab_data.keys()) else 'total_entities'
        total_entities = vocab_data.get(entity_count_key, 0)

        print(f"    {requirement_status} {prop_name}: {vocab_info} | {vocab_data['unique_values']} values | {total_entities} entities{compliance_info}")

        # Show top values if controlled vocabulary
        if vocab_data['has_controlled_vocab'] and vocab_data['values_found']:
            top_values = vocab_data['values_found'][:3]
            values_str = ", ".join([v['value'].split('/')[-1] if '/' in v['value'] else v['value'] for v in top_values])
            if len(values_str) > 60:
                values_str = values_str[:57] + "..."
            print(f"         Top values: {values_str}")

    def _get_property_requirement(self, prop_uri, class_name):
        """Get whether property is mandatory/optional in mobility spec"""
        if class_name in self.mobility_requirements:
            if prop_uri in self.mobility_requirements[class_name]['mandatory']:
                return "mandatory"
            elif prop_uri in self.mobility_requirements[class_name]['optional']:
                return "optional"
        return None

    def _get_vocabulary_info(self, vocab_data):
        """Get enhanced vocabulary information"""
        if vocab_data['unique_values'] == 0:
            return "No Values"
        elif vocab_data['has_controlled_vocab']:
            # Check if it looks like a proper codelist (URI-based values)
            if vocab_data['values_found']:
                uri_count = sum(1 for v in vocab_data['values_found'] if v['value'].startswith('http'))
                total_values = len(vocab_data['values_found'])
                if uri_count / total_values > 0.5:
                    return "Codelist"
                else:
                    return "Controlled"
            return "Controlled"
        else:
            return "Free text"

    def _generate_vocabulary_table(self):
        """Generate vocabulary summary table with properties as rows and portals as columns"""
        print("\nCONTROLLED VOCABULARY SUMMARY")
        print("-" * 80)
        
        # Get all catalogs and properties
        catalogs = sorted(self.results.keys())
        if not catalogs:
            print("No data available for vocabulary table")
            return
        
        # Include ALL configured properties, ensuring complete coverage
        vocab_properties = {}
        
        # First, get all analyzed properties
        for catalog in catalogs:
            if catalog in self.results:
                for prop_key, vocab_data in self.results[catalog].items():
                    if prop_key not in vocab_properties:
                        vocab_properties[prop_key] = {}
                    vocab_properties[prop_key][catalog] = vocab_data
        
        # Ensure all configured properties appear, even if not analyzed
        # (This handles cases where properties have no values in any catalog)
        for entity_type in ['catalogs', 'datasets', 'distributions']:
            if hasattr(self, '_configured_properties') and entity_type in self._configured_properties:
                for prop_uri in self._configured_properties[entity_type]:
                    prop_key = f"{prop_uri} ({entity_type})"
                    if prop_key not in vocab_properties:
                        vocab_properties[prop_key] = {}
        
        if not vocab_properties:
            print("No vocabulary properties found")
            return
        
        # Group properties by entity type
        entity_groups = {
            'catalogs': 'Catalog Properties',
            'datasets': 'Dataset Properties', 
            'distributions': 'Distribution Properties',
            'records': 'CatalogRecord Properties'
        }
        
        max_prop_width = 40
        
        for entity_type, group_name in entity_groups.items():
            # Get properties for this entity type that have vocabulary usage
            group_props = sorted([prop_key for prop_key in vocab_properties.keys() 
                                if f"({entity_type})" in prop_key])
            
            if not group_props:
                continue
                
            print(f"\n{group_name}:")
            
            # Header row
            header = f"| {'Property':<{max_prop_width}} |"
            for catalog in catalogs:
                header += f" {catalog} |"
            print(header)
            
            # Separator row (org-mode compliant)
            separator = f"|{'-' * (max_prop_width + 1)}|"
            for catalog in catalogs:
                separator += f"{'-' * (len(catalog) + 1)}|"
            print(separator)
            
            # Data rows
            for prop_key in group_props:
                prop_uri, entity_type_part = prop_key.rsplit(" (", 1)
                prop_name = prop_uri.split('#')[-1] if '#' in prop_uri else prop_uri.split('/')[-1]
                
                row = f"| {prop_name:<{max_prop_width}} |"
                
                for catalog in catalogs:
                    if catalog in vocab_properties[prop_key]:
                        vocab_data = vocab_properties[prop_key][catalog]
                        
                        # Get total entities and entities with this property
                        entity_count_key = [k for k in vocab_data.keys() if k.startswith('total_')][0] if any(k.startswith('total_') for k in vocab_data.keys()) else 'total_entities'
                        total_entities = vocab_data.get(entity_count_key, 0)
                        entities_with_prop = vocab_data.get('entities_with_property', 0)
                        
                        # Calculate percentage
                        if total_entities > 0:
                            percentage = (entities_with_prop / total_entities) * 100
                        else:
                            percentage = 0
                        
                        # Check if property has any values
                        if not vocab_data.get('values_found') or len(vocab_data['values_found']) == 0:
                            cell_content = f"0% (0)"
                        else:
                            # Determine vocabulary type
                            vocab_type = "F"  # Free text default
                            if vocab_data.get('has_controlled_vocab', False):
                                if vocab_data.get('values_found'):
                                    uri_count = sum(1 for v in vocab_data['values_found'] if v['value'].startswith('http'))
                                    total_values = len(vocab_data['values_found'])
                                    if uri_count / total_values > 0.5:
                                        vocab_type = "C"  # Codelist
                                    else:
                                        vocab_type = "V"  # Controlled vocabulary
                                else:
                                    vocab_type = "V"
                            
                            # Show percentage, unique values and type
                            unique_values = vocab_data.get('unique_values', 0)
                            cell_content = f"{percentage:.0f}% ({unique_values}{vocab_type})"
                    else:
                        # Property not found in this catalog or not analyzed
                        cell_content = "0% (0)"
                    
                    row += f" {cell_content} |"
                
                print(row)
        
        print("\nLegend: Y% (XC) = Y% of entities have property, X unique values, Codelist | Y% (XV) = Y% have property, X unique values, Controlled | Y% (XF) = Y% have property, X unique values, Free text")

    def _generate_extended_vocabulary_report(self):
        """Generate detailed report showing key values for vocabulary properties"""
        print("\n" + "="*80)
        print("EXTENDED VOCABULARY ANALYSIS")
        print("="*80)
        
        # Get all catalogs and vocabulary properties
        catalogs = sorted(self.results.keys())
        if not catalogs:
            print("No data available for extended report")
            return
        
        # Group properties by entity type and collect controlled vocabulary properties
        entity_groups = {
            'catalogs': 'Catalog Properties',
            'datasets': 'Dataset Properties', 
            'distributions': 'Distribution Properties',
            'records': 'CatalogRecord Properties'
        }
        
        for entity_type, group_name in entity_groups.items():
            vocab_props_found = False
            
            for catalog in catalogs:
                if catalog not in self.results:
                    continue
                    
                # Find vocabulary properties for this entity type and catalog
                vocab_props = []
                for prop_key, vocab_data in self.results[catalog].items():
                    if (f"({entity_type})" in prop_key and 
                        vocab_data.get('values_found') and 
                        len(vocab_data['values_found']) > 0 and
                        vocab_data.get('has_controlled_vocab', False)):
                        vocab_props.append((prop_key, vocab_data))
                
                if vocab_props:
                    if not vocab_props_found:
                        print(f"\n{group_name}:")
                        print("-" * len(group_name))
                        vocab_props_found = True
                    
                    # Extract meaningful catalog name
                    if '/' in catalog:
                        catalog_parts = catalog.split('/')
                        # Try to get a meaningful part, avoid empty strings
                        catalog_short = None
                        for part in reversed(catalog_parts):
                            if part and len(part) > 1:
                                catalog_short = part
                                break
                        if not catalog_short:
                            catalog_short = catalog[:50]
                    else:
                        catalog_short = catalog[:50]
                    
                    print(f"\n  {catalog_short}:")
                    
                    for prop_key, vocab_data in vocab_props:
                        prop_uri, _ = prop_key.rsplit(" (", 1)
                        prop_name = prop_uri.split('#')[-1] if '#' in prop_uri else prop_uri.split('/')[-1]
                        
                        # Determine vocabulary type
                        vocab_type = "Controlled vocabulary"
                        if vocab_data.get('values_found'):
                            uri_count = sum(1 for v in vocab_data['values_found'] if v['value'].startswith('http'))
                            total_values = len(vocab_data['values_found'])
                            if uri_count / total_values > 0.5:
                                vocab_type = "Codelist (URI-based)"
                        
                        print(f"    {prop_name} ({vocab_type}):")
                        
                        # Show top values
                        top_values = vocab_data['values_found'][:10]  # Show top 10
                        for i, value_info in enumerate(top_values, 1):
                            value = value_info['value']
                            count = value_info['count']
                            
                            # Truncate long values
                            if len(value) > 80:
                                display_value = value[:77] + "..."
                            else:
                                display_value = value
                            
                            print(f"      {i:2d}. {display_value} (used {count} times)")
                        
                        if len(vocab_data['values_found']) > 10:
                            remaining = len(vocab_data['values_found']) - 10
                            print(f"      ... and {remaining} more values")
                        
                        print()

def main():
    checker = DCATVocabularyChecker()

    # Properties that commonly use controlled vocabularies
    # based on https://mobilitydcat-ap.github.io/mobilityDCAT-AP/releases/index.html#controlled-vocabularies
    properties_to_check = {
        "datasets": [
            "https://w3id.org/mobilitydcat-ap#mobilityTheme",
            "http://www.w3.org/ns/dcat#theme",
            "http://purl.org/dc/terms/accrualPeriodicity",
            "http://purl.org/dc/terms/conformsTo",
            "http://purl.org/dc/terms/language",
            "http://purl.org/dc/terms/publisher",
            "http://purl.org/dc/terms/spatial",
            "https://w3id.org/mobilitydcat-ap#georeferencingMethod",
            "https://w3id.org/mobilitydcat-ap#networkCoverage",
            "https://w3id.org/mobilitydcat-ap#transportMode",
            "https://w3id.org/mobilitydcat-ap#intendedInformationService",
        ],
        "catalogs": [
            "http://www.w3.org/ns/dcat#themeTaxonomy",
            "http://purl.org/dc/terms/language",
            "http://purl.org/dc/terms/publisher",
            "http://purl.org/dc/terms/spatial"
        ],
        "distributions": [
            "http://purl.org/dc/terms/format",
            "http://purl.org/dc/terms/language",
            "http://purl.org/dc/terms/publisher",
            "https://w3id.org/mobilitydcat-ap#mobilityDataStandard",
            "https://w3id.org/mobilitydcat-ap#grammar",
            "https://w3id.org/mobilitydcat-ap#applicationLayerProtocol",
            "https://w3id.org/mobilitydcat-ap#communicationMethod"
        ]
    }

    print("CONTROLLED VOCABULARY ANALYZER")
    print("===============================")
    print("Analyzing controlled vocabulary usage for properties:")
    for entity_type, props in properties_to_check.items():
        for prop_uri in props:
            prop_name = prop_uri.split('#')[-1] if '#' in prop_uri else prop_uri.split('/')[-1]
            print(f"  - {prop_name} → {entity_type}")
    print()

    # Store configured properties for complete table generation
    checker._configured_properties = properties_to_check
    
    # Check properties directly without flattening to avoid overwrites
    catalog_entities = checker.get_catalog_entities()
    
    if not catalog_entities:
        print("No catalogs or datasets found in the endpoint")
        return
    
    print(f"Found {len(catalog_entities)} catalogs")
    
    # Check each property for each entity type explicitly
    for entity_type, props in properties_to_check.items():
        for prop_uri in props:
            print(f"Checking property: {prop_uri} on {entity_type}")
            checker.check_property_vocabulary(prop_uri, entity_type, catalog_entities)
    
    checker.generate_unified_report()

if __name__ == "__main__":
    main()
