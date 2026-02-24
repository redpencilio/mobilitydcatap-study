"""
Refactored MobilityDCAT-AP controlled vocabulary checker.
Operates against a specific named graph in Virtuoso.
Returns structured data instead of printing to stdout.
"""

import logging
from sparql_helpers import sparql_query

logger = logging.getLogger(__name__)

# Properties that commonly use controlled vocabularies in MobilityDCAT-AP
# https://mobilitydcat-ap.github.io/mobilityDCAT-AP/releases/index.html#controlled-vocabularies
VOCABULARY_PROPERTIES = {
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
        "http://purl.org/dc/terms/spatial",
    ],
    "distributions": [
        "http://purl.org/dc/terms/format",
        "http://purl.org/dc/terms/language",
        "http://purl.org/dc/terms/publisher",
        "https://w3id.org/mobilitydcat-ap#mobilityDataStandard",
        "https://w3id.org/mobilitydcat-ap#grammar",
        "https://w3id.org/mobilitydcat-ap#applicationLayerProtocol",
        "https://w3id.org/mobilitydcat-ap#communicationMethod",
    ],
}


def _classify_vocabulary(values: list) -> str:
    """
    Classify a list of {value, count} into C (Codelist), V (Controlled), F (Free text).
    """
    if not values:
        return "F"
    total_usage = sum(v["count"] for v in values)
    # Codelist: mostly URI values (>50%) or few unique values (<=5)
    uri_count = sum(1 for v in values if v["value"].startswith("http"))
    if len(values) <= 5 or (len(values) > 0 and uri_count / len(values) > 0.5):
        return "C"
    # Controlled: top 5 values dominate usage (>80%)
    if len(values) >= 5:
        top_usage = sum(v["count"] for v in values[:5])
        if total_usage > 0 and top_usage / total_usage > 0.8:
            return "V"
    return "F"


class VocabularyChecker:
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

    def check_property(self, property_uri: str, entity_type: str, entity_list: list) -> dict:
        """
        Analyze vocabulary usage for a property on a set of entities.
        Returns {total_entities, entities_with_property, unique_values, vocab_type, top_values}
        """
        if not entity_list:
            return {
                "total_entities": 0,
                "entities_with_property": 0,
                "unique_values": 0,
                "vocab_type": "F",
                "top_values": [],
            }

        values_clause = " ".join(f"<{e}>" for e in entity_list)

        values_q = f"""
        SELECT DISTINCT ?value (COUNT(?entity) as ?count) WHERE {{
            GRAPH <{self.graph}> {{
                VALUES ?entity {{ {values_clause} }}
                ?entity <{property_uri}> ?value .
            }}
        }}
        GROUP BY ?value
        ORDER BY DESC(?count)
        """
        count_q = f"""
        SELECT (COUNT(DISTINCT ?entity) as ?total) WHERE {{
            GRAPH <{self.graph}> {{
                VALUES ?entity {{ {values_clause} }}
                ?entity <{property_uri}> ?value .
            }}
        }}
        """

        values_result = self._q(values_q)
        count_result = self._q(count_q)

        values = []
        for b in values_result.get("results", {}).get("bindings", []):
            values.append({"value": b["value"]["value"], "count": int(b["count"]["value"])})

        entities_with = 0
        if count_result and count_result.get("results", {}).get("bindings"):
            entities_with = int(count_result["results"]["bindings"][0]["total"]["value"])

        return {
            "total_entities": len(entity_list),
            "entities_with_property": entities_with,
            "unique_values": len(values),
            "vocab_type": _classify_vocabulary(values),
            "top_values": values[:10],
        }

    def check_all_properties(self) -> dict:
        """
        Run vocabulary analysis for all configured properties.

        Returns:
        {
          "catalog_uris": [str, ...],
          "entity_types": {
            entity_type: [
              {
                "uri": str,
                "short_name": str,
                "per_catalog": {
                  catalog_uri: {
                    total_entities, entities_with_property,
                    unique_values, vocab_type, top_values
                  }
                }
              }
            ]
          }
        }
        """
        catalog_entities = self.get_catalog_entities()
        logger.info("Vocabulary check: found %d catalogs", len(catalog_entities))

        results = {
            "catalog_uris": list(catalog_entities.keys()),
            "entity_types": {},
        }

        for entity_type, prop_uris in VOCABULARY_PROPERTIES.items():
            type_results = []
            for prop_uri in prop_uris:
                short_name = prop_uri.split("#")[-1] if "#" in prop_uri else prop_uri.split("/")[-1]
                per_catalog = {}
                for catalog_uri, entities in catalog_entities.items():
                    entity_list = entities.get(entity_type, [])
                    per_catalog[catalog_uri] = self.check_property(prop_uri, entity_type, entity_list)
                type_results.append(
                    {
                        "uri": prop_uri,
                        "short_name": short_name,
                        "per_catalog": per_catalog,
                    }
                )
            results["entity_types"][entity_type] = type_results

        return results
