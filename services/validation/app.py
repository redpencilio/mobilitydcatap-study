"""
MobilityDCAT-AP Validation Service
Receives job URIs, fetches DCAT data, runs analysis, generates HTML reports.
"""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from dcat_fetcher import detect_and_fetch
from property_analysis import PropertyAnalyzer
from report_generator import generate_report
from sparql_helpers import drop_graph, sparql_query, sparql_update
from vocabulary_checker import VocabularyChecker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

SPARQL_ENDPOINT = os.environ.get("SPARQL_ENDPOINT", "http://triplestore:8890/sparql")
REPORTS_DIR = os.environ.get("REPORTS_DIR", "/reports")
BASE_REPORT_URL = os.environ.get("BASE_REPORT_URL", "http://localhost/reports")
APP_GRAPH = "http://mu.semte.ch/application"

EXT = "http://mu.semte.ch/vocabularies/ext/"
DCT = "http://purl.org/dc/terms/"
XSD = "http://www.w3.org/2001/XMLSchema#"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_job_details(job_uri: str) -> dict:
    query = f"""
    PREFIX ext: <{EXT}>
    SELECT ?sourceUrl ?graphUri WHERE {{
        GRAPH <{APP_GRAPH}> {{
            <{job_uri}> ext:sourceUrl ?sourceUrl ;
                        ext:graphUri ?graphUri .
        }}
    }}
    """
    result = sparql_query(SPARQL_ENDPOINT, query)
    bindings = result.get("results", {}).get("bindings", [])
    if not bindings:
        raise ValueError(f"Job not found in triplestore: {job_uri}")
    return {
        "source_url": bindings[0]["sourceUrl"]["value"],
        "graph_uri": bindings[0]["graphUri"]["value"],
    }


def update_job_status(job_uri: str, status: str, **kwargs) -> None:
    now = _now_iso()
    extra = ""

    if status == "running":
        extra = f'<{job_uri}> ext:startedAt "{now}"^^xsd:dateTime .\n'
    elif status in ("completed", "failed"):
        extra = f'<{job_uri}> ext:finishedAt "{now}"^^xsd:dateTime .\n'

    if "report_url" in kwargs:
        url = kwargs["report_url"].replace('"', '\\"')
        extra += f'<{job_uri}> ext:reportUrl "{url}" .\n'
    if "endpoint_type" in kwargs:
        et = kwargs["endpoint_type"].replace('"', '\\"')
        extra += f'<{job_uri}> ext:endpointType "{et}" .\n'
    if "error_message" in kwargs:
        msg = str(kwargs["error_message"])[:2000].replace('"', '\\"').replace("\n", " ")
        extra += f'<{job_uri}> ext:errorMessage "{msg}" .\n'

    update = f"""
PREFIX ext: <{EXT}>
PREFIX xsd: <{XSD}>
DELETE {{
    GRAPH <{APP_GRAPH}> {{
        <{job_uri}> ext:status ?oldStatus .
    }}
}}
INSERT {{
    GRAPH <{APP_GRAPH}> {{
        <{job_uri}> ext:status "{status}" .
        {extra}
    }}
}}
WHERE {{
    GRAPH <{APP_GRAPH}> {{
        <{job_uri}> ext:status ?oldStatus .
    }}
}}
"""
    sparql_update(SPARQL_ENDPOINT, update)
    logger.info("Job %s → %s", job_uri, status)


def process_job(job_uri: str) -> None:
    """Full job processing pipeline. Runs in a background thread."""
    try:
        # 1. Fetch job details from triplestore
        job = get_job_details(job_uri)
        source_url = job["source_url"]
        graph_uri = job["graph_uri"]
        logger.info("Processing job %s: %s", job_uri, source_url)

        update_job_status(job_uri, "running")

        # 2. Fetch DCAT data and load into named graph
        endpoint_type = detect_and_fetch(
            url=source_url,
            sparql_endpoint=SPARQL_ENDPOINT,
            graph_uri=graph_uri,
        )
        update_job_status(job_uri, "running", endpoint_type=endpoint_type)

        # 3. Property compliance analysis
        prop_analyzer = PropertyAnalyzer(SPARQL_ENDPOINT, graph_uri)
        property_results = prop_analyzer.analyze_all_properties()
        logger.info("Property analysis complete")

        # 4. Controlled vocabulary analysis
        voc_checker = VocabularyChecker(SPARQL_ENDPOINT, graph_uri)
        vocabulary_results = voc_checker.check_all_properties()
        logger.info("Vocabulary analysis complete")

        # 5. Generate HTML report
        report_filename = f"{uuid.uuid4()}.html"
        report_path = os.path.join(REPORTS_DIR, report_filename)
        generate_report(
            path=report_path,
            source_url=source_url,
            endpoint_type=endpoint_type,
            property_results=property_results,
            vocabulary_results=vocabulary_results,
        )
        logger.info("Report written to %s", report_path)

        # 6. Clean up named graph to free storage
        drop_graph(SPARQL_ENDPOINT, graph_uri)

        report_url = f"{BASE_REPORT_URL}/{report_filename}"
        update_job_status(job_uri, "completed", report_url=report_url, endpoint_type=endpoint_type)

    except Exception as exc:
        logger.exception("Job %s failed: %s", job_uri, exc)
        try:
            update_job_status(job_uri, "failed", error_message=str(exc))
        except Exception:
            logger.exception("Could not update job status to failed")


@app.route("/run-job", methods=["POST"])
def run_job():
    data = request.get_json(force=True, silent=True) or {}
    job_uri = data.get("job_uri")
    if not job_uri:
        return jsonify({"error": "job_uri is required"}), 400

    thread = threading.Thread(target=process_job, args=(job_uri,), daemon=True)
    thread.start()

    return jsonify({"status": "accepted", "job_uri": job_uri}), 202


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=os.environ.get("FLASK_DEBUG") == "1")
