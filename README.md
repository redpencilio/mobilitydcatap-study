# mobilityDCAT-AP in Practice: Compliance Analysis of European NAPs and the Belgian Reference Implementation

*Niels Vandekeybus & Michaël Dierick ([redpencil.io](https://redpencil.io)) · Jasper Beernaerts & Thien Kim Marie Hoang ([National Geographic Institute, Belgium](https://www.ngi.be))*

This repository accompanies the paper and presentation delivered at the **ITS European Congress 2026 in Istanbul**. It contains the data, analysis scripts, and results from the first systematic compliance study of [Mobility DCAT-AP](https://mobilitydcat-ap.github.io/mobilityDCAT-AP/) implementations across five European National Access Points (NAPs).

> **Try it yourself:** We turned the analysis tools from this study into a free online validator [mobility-dcat-validator.redpencil.io](https://mobility-dcat-validator.redpencil.io/)

---

## What this study is about

Mobility DCAT-AP defines how NAPs should describe mobility datasets; things like update frequency, transport mode, data standards used, and access rights. The specification distinguishes between *mandatory*, *recommended*, and *optional* properties.

Despite being mandated under the EU ITS Directive, how well NAPs actually implement this standard in practice had never been systematically evaluated. This paper presents the first comprehensive compliance analysis. Using validated and normalised RDF graphs, we assess adherence to mandatory and recommended properties, the correctness of controlled vocabulary usage, and common modelling issues that hinder interoperability. Belgium's [transportdata.be](https://transportdata.be), built on an extended CKAN stack, is examined as a reference implementation demonstrating that full mandatory compliance is achievable.

This study asks:

- Which mandatory properties are actually populated?
- Are controlled vocabularies used correctly and consistently?
- Where are the biggest gaps, and what do they mean for cross-border data access?

The five NAPs analysed:

| NAP | Country |
|-----|---------|
| [mobilitydata.at](https://mobilitydata.at) | Austria |
| [dataudveksler.app.vd.dk](https://du-portal-ui.dataudveksler.app.vd.dk/) | Denmark |
| [mobilithek.info](https://mobilithek.info) | Germany |
| [trafficdata.se](https://trafficdata.se) | Sweden |
| [transportdata.be](https://transportdata.be) | Belgium |

## Key findings

**Property coverage is uneven.** Core properties like `title`, `description`, and `publisher` are well-covered across all NAPs. But mandatory properties such as `accrualPeriodicity` (update frequency) and `accessURL` are missing on many datasets. Austria's NAP, for instance, provides no `accessURL` on any of its 23 distributions.

**Controlled vocabulary adoption is inconsistent.** Some NAPs use the correct URI-based codelists; others use free-text values or local identifiers that cannot be interpreted by machines. This breaks interoperability, a key goal of the ITS Directive.

**`mobilityTheme` is widely used but imprecisely.** The "other" category dominates in several NAPs, suggesting that the controlled vocabulary doesn't yet cover enough real-world mobility data types, or that publishers are unsure how to map their data.

The detailed results are in [`property-analysis.org`](property-analysis.org) and [`controlled-voc-analysis.org`](controlled-voc-analysis.org).

## Repository contents

```
├── its-istanbul-2026-mobility-dcat-ap-in-practice.pdf   # Conference paper
├── mobility-dcat-ap-in-practice.pptx                    # Presentation slides
│
├── mobilitydata-at-sorted.nt       # NAP data snapshots (N-Triples format)
├── mobilithek-info-sorted.nt
├── trafficdata-se-sorted.nt
├── transportdata-be-sorted.nt
├── vd-dk-sorted.nt
│
├── property-analysis/              # Checks which Mobility DCAT-AP properties are present
│   ├── property_analysis.py
│   ├── Dockerfile
│   └── run_property_analysis.sh
│
├── vocabulary-checker/             # Checks whether controlled vocabularies are used correctly
│   ├── dcat_vocabulary_checker.py
│   ├── Dockerfile
│   └── run_docker.sh
│
├── property-analysis.org           # Property analysis results
└── controlled-voc-analysis.org     # Vocabulary analysis results
```

## Running the analysis yourself

The scripts query a SPARQL endpoint loaded with the NAP data. You'll need a running [Virtuoso](https://virtuoso.openlinksw.com/) instance (or any SPARQL 1.1 endpoint) with the `.nt` files loaded.

Both tools are containerised:

```bash
# Property analysis
cd property-analysis
./run_property_analysis.sh

# Vocabulary checker
cd vocabulary-checker
./run_docker.sh
```

By default the scripts connect to `http://host.docker.internal:8890/sparql`. Adjust the `sparql_endpoint` in the Python files if your setup differs.

**Dependencies:** Docker (for the containerised runners), or Python 3 + `requests` if you run the scripts directly.

## Online validator

We have turned these analysis tools into a free, hosted online validator:

**[mobility-dcat-validator.redpencil.io](https://mobility-dcat-validator.redpencil.io/)**

Point to your NAP's Mobility DCAT-AP data and get an instant report on property coverage and vocabulary compliance, no installation needed.

---

## About the authors

This study is a collaboration between [redpencil.io](https://redpencil.io) and the [National Geographic Institute of Belgium (NGI)](https://www.ngi.be).

**redpencil.io** is a software consultancy specialising in linked data, semantic web technologies, and open standards for the public sector and mobility domain. We built transportdata.be and have been working on Mobility DCAT-AP tooling since the standard's early days.

**NGI Belgium** is the national mapping and geospatial authority of Belgium, and a key partner in Belgium's NAP and open mobility data ecosystem.

---

If you are a NAP owner, mobility data publisher, or ITS policy maker and want to discuss Mobility DCAT-AP compliance, data quality, or building tools on top of open mobility data, we'd love to hear from you:

**[redpencil.io/contact](https://redpencil.io/contact)**
