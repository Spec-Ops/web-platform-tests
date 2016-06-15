import json
import os
import urlparse

import wptserve

port = 8080
doc_root = './files/'
container_path = doc_root + 'annotations/'

# Prefer header variants
prefer_minimal = 'return=representation;include="http://www.w3.org/ns/ldp#PreferMinimalContainer"'
prefer_contained_uris = 'return=representation;include="http://www.w3.org/ns/oa#PreferContainedIRIs"'
prefer_contained_descriptions = 'return=representation;include="http://www.w3.org/ns/oa#PreferContainedDescriptions"'

collection_json = {
  "@context": [
    "http://www.w3.org/ns/anno.jsonld",
    "http://www.w3.org/ns/ldp.jsonld"
  ],
  "id": "/annotations/",
  "type": ["BasicContainer", "AnnotationCollection"],
  "total": 0,
  "label": "A Container for Web Annotations",
  "first": "/annotations/?page=0",
  "last": "/annotations/?page="
}

def load_headers_from_file(path):
    headers = []
    with open(path) as header_file:
        data = header_file.read()
        headers = [tuple(item.strip() for item in line.split(":", 1))
            for line in data.splitlines() if line]
    return headers

def populate_headers(requested_file, response):
    headers = []
    headers_file = requested_file[:-7] + '.headers'

    response.headers.update(default_headers)

    if os.path.isfile(headers_file):
        headers = load_headers_from_file(headers_file)
        for header, value in headers:
            response.headers.append(header, value)


def annotation_files():
    files = []
    for file in os.listdir(container_path):
        if file.endswith('.jsonld') and not file.startswith('index-') \
            and not file.startswith('page'):
                files.append(file);
    return files


def annotations():
    files = annotation_files()
    for file in files:
        with open(container_path + file) as annotation:
            annotations.append(json.load(file))
    return annotations


def total_annotations():
    return len(annotation_files())


default_headers = load_headers_from_file(doc_root
    + 'annotations/__dir__.headers')

@wptserve.handlers.handler
def collection(request, response):
    """Annotation Collection"""


    # Default Container format SHOULD be PreferContainedDescriptions
    prefer_header = request.headers.get('Prefer', prefer_contained_descriptions)

    collection_json['total'] = total_annotations()
    # TODO: calculate last page and add it's page number

    # only PreferContainedIRIs has unqiue content
    if prefer_header == prefer_contained_uris:
        collection_json['id'] += '?iris=1'
        collection_json['first'] += '&iris=1'

    collection_headers_file = doc_root + 'annotations/collection.headers'
    response.headers.update(load_headers_from_file(collection_headers_file))
    # this one's unique per request
    response.headers.set('Content-Location', collection_json['id'])
    return json.dumps(collection_json, indent=4, sort_keys=True)


@wptserve.handlers.handler
def single(request, response):
    """Inidividual Annotations"""
    requested_file = doc_root + request.request_path[1:] + '.jsonld';
    populate_headers(requested_file, response)

    with open(requested_file) as data_file:
        data = data_file.read()
    return data;


print 'http://localhost:{0}/'.format(port)

routes = [
    ("GET", "", wptserve.handlers.file_handler),
    ("GET", "index.html", wptserve.handlers.file_handler),
    ("GET", "annotations/", collection),
    ("GET", "annotations/*", single)
]

httpd = wptserve.server.WebTestHttpd(port=port, doc_root=doc_root,
                            routes=routes)
httpd.start(block=True)
