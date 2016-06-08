import os

import wptserve

doc_root = './files/'

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


default_headers = load_headers_from_file(doc_root
    + 'annotations/__dir__.headers')

@wptserve.handlers.handler
def collection(request, response):
    """Annotation Collection"""
    requested_file = doc_root + 'annotations/index-preferminimal.jsonld'
    populate_headers(requested_file, response)

    with open(requested_file) as data_file:
        data = data_file.read()
    return data;

@wptserve.handlers.handler
def single(request, response):
    """Inidividual Annotations"""
    requested_file = doc_root + request.request_path[1:] + '.jsonld';
    populate_headers(requested_file, response)

    with open(requested_file) as data_file:
        data = data_file.read()
    return data;

httpd = wptserve.server.WebTestHttpd(port=8080, doc_root=doc_root,
                            routes=[("GET", "annotations/", collection),
                                    ("GET", "annotations/*", single)])
httpd.start(block=True)
