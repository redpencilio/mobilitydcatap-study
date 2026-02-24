"""
DCAT endpoint auto-detection and fetching.

Supports:
  - LDES (Linked Data Event Streams) – full pagination crawl via tree:node
  - Hydra collections – follows hydra:next page links
  - CKAN DCAT API – content negotiation / format suffixes
  - Plain DCAT RDF document – generic fallback
"""

import time
import logging

import requests
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from sparql_helpers import load_rdf_into_graph

logger = logging.getLogger(__name__)

LDES_NS = "https://w3id.org/ldes#"
TREE_NS = "https://w3id.org/tree#"
HYDRA_NS = "http://www.w3.org/ns/hydra/core#"

ACCEPT_HEADER = "text/turtle, application/ld+json;q=0.9, application/rdf+xml;q=0.8, application/n-triples;q=0.7"
REQUEST_TIMEOUT = 60


def _parse_graph(content: str | bytes, content_type: str) -> Graph:
    """Parse RDF content into an rdflib Graph based on Content-Type."""
    g = Graph()
    ct = content_type.lower()
    if "turtle" in ct:
        fmt = "turtle"
    elif "json" in ct:
        fmt = "json-ld"
    elif "xml" in ct or "rdf" in ct:
        fmt = "xml"
    elif "n-triples" in ct or "plain" in ct:
        fmt = "nt"
    else:
        # Try turtle as default, fall back to others
        for fmt in ("turtle", "xml", "json-ld", "nt"):
            try:
                g2 = Graph()
                g2.parse(data=content, format=fmt)
                return g2
            except Exception:
                continue
        raise ValueError(f"Cannot parse RDF with content-type: {content_type}")
    g.parse(data=content, format=fmt)
    return g


def detect_endpoint_type(url: str) -> str:
    """
    Probe the URL to determine the DCAT endpoint type.
    Returns one of: 'ldes', 'hydra', 'ckan', 'dcat'
    """
    if "/api/3/action/" in url or ("ckan" in url.lower() and "/catalog" not in url.lower()):
        return "ckan"

    try:
        resp = requests.get(url, headers={"Accept": ACCEPT_HEADER}, timeout=REQUEST_TIMEOUT)
        content_type = resp.headers.get("Content-Type", "text/turtle")
        g = _parse_graph(resp.text, content_type)

        # Check for LDES markers
        if (
            any(g.triples((None, URIRef(f"{TREE_NS}relation"), None)))
            or any(g.triples((None, RDF.type, URIRef(f"{LDES_NS}EventStream"))))
            or any(g.triples((None, URIRef(f"{TREE_NS}node"), None)))
        ):
            return "ldes"

        # Check for Hydra markers
        if any(g.triples((None, URIRef(f"{HYDRA_NS}view"), None))) or any(
            g.triples((None, RDF.type, URIRef(f"{HYDRA_NS}Collection")))
        ):
            return "hydra"

    except Exception as e:
        logger.warning("Endpoint detection probe failed for %s: %s", url, e)

    return "dcat"


def fetch_ldes(url: str) -> Graph:
    """Crawl all pages of an LDES stream via tree:node links."""
    combined = Graph()
    visited: set[str] = set()
    frontier: set[str] = {url}

    while frontier:
        current_url = frontier.pop()
        if current_url in visited:
            continue
        visited.add(current_url)

        try:
            resp = requests.get(
                current_url,
                headers={"Accept": ACCEPT_HEADER},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "text/turtle")
            page_graph = _parse_graph(resp.text, content_type)
            combined += page_graph

            for _, _, next_node in page_graph.triples((None, URIRef(f"{TREE_NS}node"), None)):
                next_url = str(next_node)
                if next_url not in visited:
                    frontier.add(next_url)

            logger.info("LDES: fetched %s (%d triples so far)", current_url, len(combined))
            time.sleep(0.5)  # polite crawling

        except Exception as e:
            logger.warning("LDES: failed to fetch page %s: %s", current_url, e)

    return combined


def fetch_hydra(url: str) -> Graph:
    """Fetch all pages of a Hydra paginated collection."""
    combined = Graph()
    current_url: str | None = url

    while current_url:
        resp = requests.get(current_url, headers={"Accept": ACCEPT_HEADER}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "text/turtle")
        page_graph = _parse_graph(resp.text, content_type)
        combined += page_graph

        # Find hydra:next
        next_url = None
        for s in page_graph.subjects(RDF.type, URIRef(f"{HYDRA_NS}PartialCollectionView")):
            for _, _, obj in page_graph.triples((s, URIRef(f"{HYDRA_NS}next"), None)):
                next_url = str(obj)
        # Also check direct hydra:next on the collection
        if not next_url:
            for _, _, obj in page_graph.triples((None, URIRef(f"{HYDRA_NS}next"), None)):
                next_url = str(obj)
                break

        logger.info("Hydra: fetched %s (%d triples so far)", current_url, len(combined))
        current_url = next_url

    return combined


def fetch_ckan(url: str) -> Graph:
    """Fetch from a CKAN DCAT endpoint using format suffixes and content negotiation."""
    base = url.rstrip("/")

    for suffix, mime, fmt in [
        (".ttl", "text/turtle", "turtle"),
        (".rdf", "application/rdf+xml", "xml"),
        (".jsonld", "application/ld+json", "json-ld"),
        (".n3", "text/n3", "n3"),
    ]:
        try_url = base + suffix if not base.endswith(suffix) else base
        try:
            resp = requests.get(try_url, headers={"Accept": mime}, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                g = Graph()
                g.parse(data=resp.text, format=fmt)
                logger.info("CKAN: fetched %s as %s (%d triples)", try_url, fmt, len(g))
                return g
        except Exception:
            continue

    # Fallback: content negotiation on original URL
    resp = requests.get(url, headers={"Accept": ACCEPT_HEADER}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "text/turtle")
    return _parse_graph(resp.text, content_type)


def fetch_plain_dcat(url: str) -> Graph:
    """Fetch a plain DCAT RDF document with content negotiation."""
    for mime, fmt in [
        ("text/turtle", "turtle"),
        ("application/rdf+xml", "xml"),
        ("application/ld+json", "json-ld"),
        ("application/n-triples", "nt"),
    ]:
        try:
            resp = requests.get(url, headers={"Accept": mime}, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                g = Graph()
                g.parse(data=resp.text, format=fmt)
                logger.info("Plain DCAT: fetched %s as %s (%d triples)", url, fmt, len(g))
                return g
        except Exception:
            continue

    raise ValueError(f"Could not fetch any RDF from {url}")


def detect_and_fetch(url: str, sparql_endpoint: str, graph_uri: str) -> str:
    """
    Detect endpoint type, fetch all RDF data, and load into a Virtuoso named graph.
    Returns the detected endpoint type string.
    """
    endpoint_type = detect_endpoint_type(url)
    logger.info("Detected endpoint type: %s for %s", endpoint_type, url)

    if endpoint_type == "ldes":
        graph = fetch_ldes(url)
    elif endpoint_type == "hydra":
        graph = fetch_hydra(url)
    elif endpoint_type == "ckan":
        graph = fetch_ckan(url)
    else:
        graph = fetch_plain_dcat(url)

    logger.info("Fetched %d total triples, loading into %s", len(graph), graph_uri)

    # Serialize as N-Triples for reliable loading into Virtuoso
    nt_data = graph.serialize(format="nt").encode("utf-8")
    load_rdf_into_graph(sparql_endpoint, graph_uri, nt_data, content_type="application/n-triples")

    logger.info("Loaded graph %s successfully", graph_uri)
    return endpoint_type
