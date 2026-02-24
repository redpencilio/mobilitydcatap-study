curl --location --request GET 'https://www.mobilitydata.gv.at/api/mobility_dcat/en'  > mobilitydata.rdf
curl --location --request GET 'https://mobilithek.info/mobilithek/api/v1.0/export/datasets/mobilitydcatap?page=0&size=100' --header 'Accept: text/turtle' > mobilithek.info.ttl
curl --location --request GET 'https://businessservice.dataudveksler.app.vd.dk/api/Metadata?format=dcat' --header 'Accept: text/turtle' > vd.dk.ttl
