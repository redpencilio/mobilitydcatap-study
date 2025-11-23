#!/usr/bin/env python3

import requests
from urllib.parse import quote
import json
from collections import defaultdict

class DCATPropertyAnalyzer:
    def __init__(self, sparql_endpoint="http://host.docker.internal:8890/sparql"):
        self.sparql_endpoint = sparql_endpoint
        self.results = defaultdict(dict)
        self.mobility_spec = self._load_mobility_spec()

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
        """Get all catalogs and their associated entities"""
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

    def _load_mobility_spec(self):
        """Load all properties from mobilityDCAT-AP specification"""
        # using https://mobilitydcat-ap.github.io/mobilityDCAT-AP/releases/index.html#mobilitydcat-ap-classes-and-properties
        return {
            "dcat:Catalog": {
                "mandatory": [
                    "http://purl.org/dc/terms/description",
                    "http://purl.org/dc/terms/spatial",
                    "http://xmlns.com/foaf/0.1/homepage",
                    "http://purl.org/dc/terms/publisher",
                    "http://www.w3.org/ns/dcat#record",
                    "http://purl.org/dc/terms/title"
                ],
                "recommended": [
                    "http://purl.org/dc/terms/language",
                    "http://purl.org/dc/terms/license",
                    "http://purl.org/dc/terms/modified",
                    "http://purl.org/dc/terms/issued",
                    "http://www.w3.org/ns/dcat#themeTaxonomy"
                ],
                "optional": [
                    "http://www.w3.org/ns/dcat#dataset",
                    "http://purl.org/dc/terms/hasPart",
                    "http://purl.org/dc/terms/identifier",
                    "http://www.w3.org/ns/adms#identifier"
                ]
            },
            "dcat:Dataset": {
                "mandatory": [
                    "http://www.w3.org/ns/dcat#distribution",
                    "http://purl.org/dc/terms/description",
                    "http://purl.org/dc/terms/accrualPeriodicity",
                    "http://purl.org/dc/terms/spatial",
                    "https://w3id.org/mobilitydcat-ap#mobilityTheme",
                    "http://purl.org/dc/terms/publisher",
                    "http://purl.org/dc/terms/title"
                ],
                "recommended":
                [
                    "https://w3id.org/mobilitydcat-ap#georeferencingMethod",
                    "http://www.w3.org/ns/dcat#contactPoint",
                    "http://www.w3.org/ns/dcat#keyword",
                    "https://w3id.org/mobilitydcat-ap#networkCoverage",
                    "http://purl.org/dc/terms/conformsTo",
                    "http://purl.org/dc/terms/rightsHolder",
                    "http://purl.org/dc/terms/temporal",
                    "http://www.w3.org/ns/dcat#theme",
                    "https://w3id.org/mobilitydcat-ap#transportMode"
                ],
                "optional": [
                    "http://data.europa.eu/r5r/#applicableLegislation",
                    "https://w3id.org/mobilitydcat-ap#assessmentResult",
                    "http://purl.org/dc/terms/hasVersion",
                    "http://purl.org/dc/terms/identifier",
                    "https://w3id.org/mobilitydcat-ap#intendedInformationService",
                    "http://purl.org/dc/terms/isReferencedBy",
                    "http://purl.org/dc/terms/isVersionOf",
                    "http://purl.org/dc/terms/language",
                    "http://www.w3.org/ns/adms#identifier",
                    "http://purl.org/dc/terms/relation",
                    "http://purl.org/dc/terms/issued",
                    "http://purl.org/dc/terms/modified",
                    "http://www.w3.org/2002/07/owl#versionInfo",
                    "http://www.w3.org/ns/adms#versionNotes",
                    "http://www.w3.org/ns/dqv#hasQualityAnnotation"
                ]
            },
            "dcat:Distribution": {
                "mandatory": [
                    "http://www.w3.org/ns/dcat#accessURL",
                    "https://w3id.org/mobilitydcat-ap#mobilityDataStandard",
                    "http://purl.org/dc/terms/format",
                    "http://purl.org/dc/terms/rights"
                ],
                "recommended": [
                    "https://w3id.org/mobilitydcat-ap#applicationLayerProtocol",
                    "http://purl.org/dc/terms/description",
                    "http://purl.org/dc/terms/license"
                ],
                "optional": [
                    "http://www.w3.org/ns/dcat#accessService",
#                    "http://data.europa.eu/r5r/dcatap#applicableLegislation",
                    "http://www.w3.org/2011/content#characterEncoding",
                    "https://w3id.org/mobilitydcat-ap#communicationMethod",
                    "https://w3id.org/mobilitydcat-ap#dataFormatNotes",
                    "http://www.w3.org/ns/dcat#downloadURL",
                    "https://w3id.org/mobilitydcat-ap#grammar",
                    "http://www.w3.org/ns/adms#sample",
                    "http://purl.org/dc/terms/temporal",
                ]
            },
            "dcat:CatalogRecord": {
                "mandatory": [
                    "http://purl.org/dc/terms/created",
                    "http://purl.org/dc/terms/language",
                    "http://purl.org/dc/terms/modified",
                    "http://xmlns.com/foaf/0.1/primaryTopic"
                ],
                "optional": [
                    "http://purl.org/dc/terms/publisher",
                    "http://purl.org/dc/terms/source"
                ]
            }
        }

    def analyze_property(self, property_uri, entity_type, catalog_entities):
        """Analyze a specific property across all catalogs"""
        entity_type_map = {
            'dcat:Catalog': 'catalogs',
            'dcat:Dataset': 'datasets', 
            'dcat:Distribution': 'distributions',
            'dcat:CatalogRecord': 'records'
        }
        
        entity_list_key = entity_type_map[entity_type]
        
        for catalog, entities in catalog_entities.items():
            entity_list = entities.get(entity_list_key, [])
            
            if not entity_list:
                # Store zero counts for catalogs without entities of this type
                self.results[catalog][f"{property_uri} ({entity_type})"] = {
                    'entities_with_property': 0,
                    'total_entities': 0
                }
                continue

            entity_filter = ' '.join([f"<{entity}>" for entity in entity_list])

            query = f"""
            SELECT (COUNT(DISTINCT ?entity) as ?count) WHERE {{
                VALUES ?entity {{ {entity_filter} }}
                ?entity <{property_uri}> ?value .
            }}
            """

            result = self.execute_sparql(query)
            entities_with_property = 0
            
            if result and result.get('results', {}).get('bindings'):
                entities_with_property = int(result['results']['bindings'][0]['count']['value'])

            self.results[catalog][f"{property_uri} ({entity_type})"] = {
                'entities_with_property': entities_with_property,
                'total_entities': len(entity_list)
            }

    def analyze_all_properties(self):
        """Analyze all properties from the mobility specification"""
        catalog_entities = self.get_catalog_entities()
        
        if not catalog_entities:
            print("No catalogs found in the endpoint")
            return
        
        print(f"Found {len(catalog_entities)} catalogs")
        
        # Analyze all properties for each class
        for class_name, properties in self.mobility_spec.items():
            print(f"Analyzing {class_name} properties...")
            
            # Check mandatory properties
            for prop_uri in properties['mandatory']:
                self.analyze_property(prop_uri, class_name, catalog_entities)
            
            # Check recommended properties  
            if 'recommended' in properties:
                for prop_uri in properties['recommended']:
                    self.analyze_property(prop_uri, class_name, catalog_entities)
            
            # Check optional properties  
            for prop_uri in properties['optional']:
                self.analyze_property(prop_uri, class_name, catalog_entities)
        
        self.generate_property_table()

    def generate_property_table(self):
        """Generate org-style table with catalogs as columns and properties as rows"""
        print("\n" + "="*100)
        print("MOBILITY DCAT-AP PROPERTY ANALYSIS")
        print("="*100)
        
        # Get all catalogs
        catalogs = sorted(self.results.keys())
        if not catalogs:
            print("No data available for property table")
            return
        
        # No truncation, just use full catalog URIs
        max_prop_width = 40
        
        # Group properties by entity type
        entity_groups = {
            'dcat:Catalog': 'Catalog Properties',
            'dcat:Dataset': 'Dataset Properties', 
            'dcat:Distribution': 'Distribution Properties',
            'dcat:CatalogRecord': 'CatalogRecord Properties'
        }
        
        for class_name, group_name in entity_groups.items():
            print(f"\n{group_name}:")
            print("-" * len(group_name))
            
            # Get all properties for this class (mandatory + recommended + optional)
            all_props = []
            if class_name in self.mobility_spec:
                all_props.extend([(prop, 'M') for prop in self.mobility_spec[class_name]['mandatory']])
                if 'recommended' in self.mobility_spec[class_name]:
                    all_props.extend([(prop, 'R') for prop in self.mobility_spec[class_name]['recommended']])
                all_props.extend([(prop, 'O') for prop in self.mobility_spec[class_name]['optional']])
            
            if not all_props:
                continue
            
            # Header row
            header = f"| {'Property (M/R/O)':<{max_prop_width}} |"
            for catalog in catalogs:
                header += f" {catalog} |"
            print(header)
            
            # Separator row (org-style)
            separator = f"|{'-' * (max_prop_width + 1)}+"
            for catalog in catalogs:
                separator += f"{'-' * (len(catalog) + 1)}+"
            print(separator)
            
            # Data rows
            for prop_uri, requirement_type in all_props:
                prop_name = prop_uri.split('#')[-1] if '#' in prop_uri else prop_uri.split('/')[-1]
                
                # Truncate property name if too long and add requirement type
                if len(prop_name) > max_prop_width - 4:
                    prop_name = prop_name[:max_prop_width-7] + "..."
                prop_display = f"{prop_name} ({requirement_type})"
                
                row = f"| {prop_display:<{max_prop_width}} |"
                
                for catalog in catalogs:
                    prop_key = f"{prop_uri} ({class_name})"
                    
                    if catalog in self.results and prop_key in self.results[catalog]:
                        data = self.results[catalog][prop_key]
                        entities_with_prop = data['entities_with_property']
                        total_entities = data['total_entities']
                        
                        if total_entities > 0:
                            cell_content = f"{entities_with_prop}/{total_entities}"
                        else:
                            cell_content = "N/A"
                    else:
                        cell_content = "-"
                    
                    row += f" {cell_content} |"
                
                print(row)
        
        print("\nLegend:")
        print("(M) = Mandatory property")
        print("(R) = Recommended property")
        print("(O) = Optional property")
        print("N/A = No entities of this type in catalog")
        print("- = Property not checked")

def main():
    analyzer = DCATPropertyAnalyzer()
    
    print("MOBILITY DCAT-AP PROPERTY ANALYZER")
    print("==================================")
    print("This tool analyzes property usage across all catalogs")
    print("for all mandatory and optional properties defined in")
    print("the mobilityDCAT-AP specification.")
    print()
    
    analyzer.analyze_all_properties()

if __name__ == "__main__":
    main()
