"""
Refactored MobilityDCAT-AP property analyzer.
Operates against a specific named graph in Virtuoso instead of the entire store.
Returns structured data instead of printing to stdout.
"""

import logging
from collections import defaultdict
from sparql_helpers import sparql_query

logger = logging.getLogger(__name__)

MOBILITY_SPEC = {
    "dcat:Catalog": {
        "mandatory": [
            "http://purl.org/dc/terms/description",
            "http://purl.org/dc/terms/spatial",
            "http://xmlns.com/foaf/0.1/homepage",
            "http://purl.org/dc/terms/publisher",
            "http://www.w3.org/ns/dcat#record",
            "http://purl.org/dc/terms/title",
        ],
        "recommended": [
            "http://purl.org/dc/terms/language",
            "http://purl.org/dc/terms/license",
            "http://purl.org/dc/terms/modified",
            "http://purl.org/dc/terms/issued",
            "http://www.w3.org/ns/dcat#themeTaxonomy",
        ],
        "optional": [
            "http://www.w3.org/ns/dcat#dataset",
            "http://purl.org/dc/terms/hasPart",
            "http://purl.org/dc/terms/identifier",
            "http://www.w3.org/ns/adms#identifier",
        ],
    },
    "dcat:Dataset": {
        "mandatory": [
            "http://www.w3.org/ns/dcat#distribution",
            "http://purl.org/dc/terms/description",
            "http://purl.org/dc/terms/accrualPeriodicity",
            "http://purl.org/dc/terms/spatial",
            "https://w3id.org/mobilitydcat-ap#mobilityTheme",
            "http://purl.org/dc/terms/publisher",
            "http://purl.org/dc/terms/title",
        ],
        "recommended": [
            "https://w3id.org/mobilitydcat-ap#georeferencingMethod",
            "http://www.w3.org/ns/dcat#contactPoint",
            "http://www.w3.org/ns/dcat#keyword",
            "https://w3id.org/mobilitydcat-ap#networkCoverage",
            "http://purl.org/dc/terms/conformsTo",
            "http://purl.org/dc/terms/rightsHolder",
            "http://purl.org/dc/terms/temporal",
            "http://www.w3.org/ns/dcat#theme",
            "https://w3id.org/mobilitydcat-ap#transportMode",
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
            "http://www.w3.org/ns/dqv#hasQualityAnnotation",
        ],
    },
    "dcat:Distribution": {
        "mandatory": [
            "http://www.w3.org/ns/dcat#accessURL",
            "https://w3id.org/mobilitydcat-ap#mobilityDataStandard",
            "http://purl.org/dc/terms/format",
            "http://purl.org/dc/terms/rights",
        ],
        "recommended": [
            "https://w3id.org/mobilitydcat-ap#applicationLayerProtocol",
            "http://purl.org/dc/terms/description",
            "http://purl.org/dc/terms/license",
        ],
        "optional": [
            "http://www.w3.org/ns/dcat#accessService",
            "http://www.w3.org/2011/content#characterEncoding",
            "https://w3id.org/mobilitydcat-ap#communicationMethod",
            "https://w3id.org/mobilitydcat-ap#dataFormatNotes",
            "http://www.w3.org/ns/dcat#downloadURL",
            "https://w3id.org/mobilitydcat-ap#grammar",
            "http://www.w3.org/ns/adms#sample",
            "http://purl.org/dc/terms/temporal",
        ],
    },
    "dcat:CatalogRecord": {
        "mandatory": [
            "http://purl.org/dc/terms/created",
            "http://purl.org/dc/terms/language",
            "http://purl.org/dc/terms/modified",
            "http://xmlns.com/foaf/0.1/primaryTopic",
        ],
        "recommended": [],
        "optional": [
            "http://purl.org/dc/terms/publisher",
            "http://purl.org/dc/terms/source",
        ],
    },
}

CLASS_TO_ENTITY_TYPE = {
    "dcat:Catalog": "catalogs",
    "dcat:Dataset": "datasets",
    "dcat:Distribution": "distributions",
    "dcat:CatalogRecord": "records",
}


class PropertyAnalyzer:
    def __init__(self, sparql_endpoint: str, graph_uri: str):
        self.endpoint = sparql_endpoint
        self.graph = graph_uri

    def _q(self, query: str) -> dict:
        return sparql_query(self.endpoint, query)

    def get_catalog_entities(self) -> dict:
        """Return dict: {catalog_uri: {catalogs, datasets, distributions, records}}"""
        catalog_q = f"""
        PREFIX dcat: <http://www.w3.org/ns/dcat#>
        SELECT DISTINCT ?catalog WHERE {{
            GRAPH <{self.graph}> {{ ?catalog a dcat:Catalog . }}
        }}
        """
        result = self._q(catalog_q)
        catalog_entities = {}

        for binding in result.get("results", {}).get("bindings", []):
            catalog = binding["catalog"]["value"]
            catalog_entities[catalog] = {
                "catalogs": [catalog],
                "datasets": [],
                "distributions": [],
                "records": [],
            }

            dataset_q = f"""
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            SELECT DISTINCT ?dataset ?distribution WHERE {{
                GRAPH <{self.graph}> {{
                    <{catalog}> a dcat:Catalog .
                    {{ <{catalog}> dcat:dataset ?dataset . }}
                    UNION
                    {{ <{catalog}> dcat:Dataset ?dataset . }}
                    ?dataset a dcat:Dataset .
                    OPTIONAL {{
                        ?dataset dcat:distribution ?distribution .
                        ?distribution a dcat:Distribution .
                    }}
                }}
            }}
            """
            ds_result = self._q(dataset_q)
            for b in ds_result.get("results", {}).get("bindings", []):
                ds = b["dataset"]["value"]
                if ds not in catalog_entities[catalog]["datasets"]:
                    catalog_entities[catalog]["datasets"].append(ds)
                if "distribution" in b and b["distribution"]:
                    dist = b["distribution"]["value"]
                    if dist not in catalog_entities[catalog]["distributions"]:
                        catalog_entities[catalog]["distributions"].append(dist)

            record_q = f"""
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            SELECT DISTINCT ?record WHERE {{
                GRAPH <{self.graph}> {{
                    <{catalog}> dcat:record ?record .
                    ?record a dcat:CatalogRecord .
                }}
            }}
            """
            rec_result = self._q(record_q)
            for b in rec_result.get("results", {}).get("bindings", []):
                rec = b["record"]["value"]
                if rec not in catalog_entities[catalog]["records"]:
                    catalog_entities[catalog]["records"].append(rec)

        return catalog_entities

    def analyze_property(self, property_uri: str, class_name: str, entity_list: list) -> dict:
        """Return {entities_with_property, total_entities} for a property across given entities."""
        if not entity_list:
            return {"entities_with_property": 0, "total_entities": 0}

        values_clause = " ".join(f"<{e}>" for e in entity_list)
        q = f"""
        SELECT (COUNT(DISTINCT ?entity) as ?count) WHERE {{
            GRAPH <{self.graph}> {{
                VALUES ?entity {{ {values_clause} }}
                ?entity <{property_uri}> ?value .
            }}
        }}
        """
        result = self._q(q)
        count = 0
        if result and result.get("results", {}).get("bindings"):
            count = int(result["results"]["bindings"][0]["count"]["value"])

        return {"entities_with_property": count, "total_entities": len(entity_list)}

    def analyze_all_properties(self) -> dict:
        """
        Run property analysis for all MobilityDCAT-AP classes.

        Returns:
        {
          "catalogs": {catalog_uri: {...}},
          "summary": {
            class_name: {
              requirement_level: [
                {
                  "uri": str,
                  "short_name": str,
                  "requirement": "M"|"R"|"O",
                  "per_catalog": {catalog_uri: {entities_with_property, total_entities}}
                }
              ]
            }
          }
        }
        """
        catalog_entities = self.get_catalog_entities()
        logger.info("Property analysis: found %d catalogs", len(catalog_entities))

        results = {
            "catalog_uris": list(catalog_entities.keys()),
            "classes": {},
        }

        for class_name, spec in MOBILITY_SPEC.items():
            entity_key = CLASS_TO_ENTITY_TYPE[class_name]
            class_results = {}

            for req_level in ("mandatory", "recommended", "optional"):
                level_results = []
                for prop_uri in spec.get(req_level, []):
                    short_name = prop_uri.split("#")[-1] if "#" in prop_uri else prop_uri.split("/")[-1]
                    per_catalog = {}
                    for catalog_uri, entities in catalog_entities.items():
                        entity_list = entities.get(entity_key, [])
                        per_catalog[catalog_uri] = self.analyze_property(prop_uri, class_name, entity_list)
                    level_results.append(
                        {
                            "uri": prop_uri,
                            "short_name": short_name,
                            "requirement": req_level[0].upper(),  # M/R/O
                            "per_catalog": per_catalog,
                        }
                    )
                class_results[req_level] = level_results

            results["classes"][class_name] = class_results

        return results
