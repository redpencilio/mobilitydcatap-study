import requests


def sparql_query(endpoint: str, query: str) -> dict:
    """Execute a SPARQL SELECT/ASK query, return parsed JSON results."""
    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = requests.post(endpoint, headers=headers, data={"query": query}, timeout=120)
    resp.raise_for_status()
    return resp.json()


def sparql_update(endpoint: str, update: str) -> None:
    """Execute a SPARQL UPDATE statement."""
    headers = {"Content-Type": "application/sparql-update"}
    # Virtuoso uses /sparql for both query and update
    resp = requests.post(endpoint, headers=headers, data=update, timeout=120)
    resp.raise_for_status()


def load_rdf_into_graph(endpoint: str, graph_uri: str, rdf_data: bytes, content_type: str = "text/turtle") -> None:
    """Load RDF bytes into a Virtuoso named graph via Graph Store HTTP Protocol."""
    # Virtuoso GSP endpoint: replace /sparql with /sparql-graph-crud-auth (or /sparql-graph-crud)
    gsp_url = endpoint.replace("/sparql", "/sparql-graph-crud-auth")
    resp = requests.put(
        gsp_url,
        params={"graph-uri": graph_uri},
        headers={"Content-Type": content_type},
        data=rdf_data,
        timeout=300,
    )
    if resp.status_code == 404:
        # Fall back to unauthenticated GSP endpoint
        gsp_url = endpoint.replace("/sparql", "/sparql-graph-crud")
        resp = requests.put(
            gsp_url,
            params={"graph-uri": graph_uri},
            headers={"Content-Type": content_type},
            data=rdf_data,
            timeout=300,
        )
    resp.raise_for_status()


def drop_graph(endpoint: str, graph_uri: str) -> None:
    """Drop a named graph from Virtuoso."""
    sparql_update(endpoint, f"DROP SILENT GRAPH <{graph_uri}>")
