import json
import os
import urlparse
import uuid

import wptserve

port = 8080
doc_root = './files/'
container_path = doc_root + 'annotations/'

per_page = 10

MEDIA_TYPE = 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"'
# Prefer header variants
prefer_minimal = 'return=representation;' \
        + 'include="http://www.w3.org/ns/ldp#PreferMinimalContainer"'
prefer_contained_iris = 'return=representation;' \
        + 'include="http://www.w3.org/ns/oa#PreferContainedIRIs"'
prefer_contained_descriptions = 'return=representation;' \
        + 'include="http://www.w3.org/ns/oa#PreferContainedDescriptions"'


def dump_json(obj):
    return json.dumps(obj, indent=4, sort_keys=True)


def load_headers_from_file(path):
    headers = []
    with open(path) as header_file:
        data = header_file.read()
        headers = [tuple(item.strip() for item in line.split(":", 1))
                   for line in data.splitlines() if line]
    return headers


def annotation_files():
    files = []
    for file in os.listdir(container_path):
        if file.endswith('.jsonld') or file.endswith('.json'):
            files.append(file)
    return files


def annotation_iris(skip):
    iris = []
    for filename in annotation_files():
        iris.append('/annotations/' + filename)
    return iris[skip:][:per_page]


def annotations(skip):
    annotations = []
    files = annotation_files()
    for file in files:
        with open(container_path + file) as annotation:
            annotations.append(json.load(annotation))
    return annotations


def total_annotations():
    return len(annotation_files())


@wptserve.handlers.handler
def collection(request, response):
    """Annotation Collection"""

    collection_json = {
      "@context": [
        "http://www.w3.org/ns/anno.jsonld",
        "http://www.w3.org/ns/ldp.jsonld"
      ],
      "id": "/annotations/",
      "type": ["BasicContainer", "AnnotationCollection"],
      "total": 0,
      "label": "A Container for Web Annotations",
      "first": "/annotations/?page=0"
    }

    last_page = (total_annotations() / per_page) - 1
    collection_json['last'] = "/annotations/?page={0}".format(last_page)

    # Paginate if requested
    qs = urlparse.parse_qs(request.url_parts.query)
    if 'page' in qs:
        return page(request, response)

    # Default Container format SHOULD be PreferContainedDescriptions
    prefer_header = request.headers.get('Prefer',
                                        prefer_contained_descriptions)

    collection_json['total'] = total_annotations()
    # TODO: calculate last page and add it's page number

    # only PreferContainedIRIs has unqiue content
    if prefer_header == prefer_contained_iris:
        collection_json['id'] += '?iris=1'
        collection_json['first'] += '&iris=1'

    collection_headers_file = doc_root + 'annotations/collection.headers'
    response.headers.update(load_headers_from_file(collection_headers_file))
    # this one's unique per request
    response.headers.set('Content-Location', collection_json['id'])
    return dump_json(collection_json)


@wptserve.handlers.handler
def collection_head(request, response):
    container_path = doc_root + request.request_path
    if os.path.isdir(container_path):
        response.writer.write_status(200)
    else:
        response.writer.write_status(404)

    headers_file = doc_root + 'annotations/collection.headers'
    headers = load_headers_from_file(headers_file)

    for header, value in headers:
        response.writer.write_header(header, value)
    response.writer.end_headers()
    response.writer.close_connection = True


def page(request, response):
    page_json = {
      "@context": "http://www.w3.org/ns/anno.jsonld",
      "id": "/annotations/",
      "type": "AnnotationPage",
      "partOf": {
        "id": "/annotations/",
        "total": 42023
      },
      "next": "/annotations/",
      "items": [
      ]
    }

    headers_file = doc_root + 'annotations/collection.headers'
    response.headers.update(load_headers_from_file(headers_file))

    qs = urlparse.parse_qs(request.url_parts.query)
    page_num = int(qs.get('page')[0])
    page_json['id'] += '?page={0}'.format(page_num)

    total = total_annotations()
    so_far = (per_page * (page_num+1))
    remaining = total - so_far

    if page_num != 0:
        page_json['prev'] = '/annotations/?page={0}'.format(page_num-1)

    page_json['partOf']['total'] = total

    if remaining > per_page:
        page_json['next'] += '?page={0}'.format(page_num+1)
    else:
        del page_json['next']

    if qs.get('iris') and qs.get('iris')[0] is '1':
        page_json['items'] = annotation_iris(so_far)
        page_json['id'] += '&iris=1'
        if 'prev' in page_json:
            page_json['prev'] += '&iris=1'
        if 'next' in page_json:
            page_json['next'] += '&iris=1'
    else:
        page_json['items'] = annotations(so_far)

    return dump_json(page_json)


@wptserve.handlers.handler
def single(request, response):
    """Inidividual Annotations"""
    requested_file = doc_root + request.request_path[1:]

    headers_file = doc_root + 'annotations/annotation.headers'
    response.headers.update(load_headers_from_file(headers_file))

    if os.path.isfile(requested_file):
        with open(requested_file) as data_file:
            data = data_file.read()
        return data
    else:
        return (404, [], 'Not Found')


@wptserve.handlers.handler
def single_head(request, response):
    requested_file = doc_root + request.request_path[1:]
    headers_file = doc_root + 'annotations/annotation.headers'
    if os.path.isfile(requested_file):
        response.writer.write_status(200)
    else:
        response.writer.write_status(404)

    headers = load_headers_from_file(headers_file)
    #response.headers.update(headers)
    for header, value in headers:
        response.writer.write_header(header, value)
    response.writer.end_headers()
    response.writer.close_connection = True

@wptserve.handlers.handler
def single_options(request, response):
    requested_file = doc_root + request.request_path[1:]
    headers_file = doc_root + 'annotations/annotation.headers'
    if os.path.isfile(requested_file):
        response.writer.write_status(200)
    else:
        response.writer.write_status(404)

    response.writer.write_header('Access-Control-Allow-Origin', '*')
    response.writer.end_headers()
    response.writer.close_connection = True

@wptserve.handlers.handler
def create_annotation(request, response):
    # TODO: verify media type is JSON of some kind (at least)
    incoming = json.loads(request.body)
    id = str(uuid.uuid4())
    if 'id' in incoming:
        incoming['canonical'] = incoming['id']
    incoming['id'] = '/annotations/' + id

    with open(container_path + id, 'w') as outfile:
        json.dump(incoming, outfile)

    # TODO: rashly assuming the above worked...of course
    return (201,
            [('Content-Type', MEDIA_TYPE), ('Location', incoming['id'])],
            dump_json(incoming))


@wptserve.handlers.handler
def delete_annotation(request, response):
    requested_file = doc_root + request.request_path[1:]
    if os.remove(requested_file):
        return (204, [], '')


print 'http://localhost:{0}/'.format(port)

routes = [
    ("GET", "", wptserve.handlers.file_handler),
    ("GET", "index.html", wptserve.handlers.file_handler),

    # container responses
    ("HEAD", "annotations/", collection_head),
    ("GET", "annotations/", collection),
    ("POST", "annotations/", create_annotation),

    # single annotation responses
    ("HEAD", "annotations/*", single_head),
    ("OPTIONS", "annotations/*", single_options),
    ("GET", "annotations/*", single),
    ("DELETE", "annotations/*", delete_annotation)
]

httpd = wptserve.server.WebTestHttpd(port=port, doc_root=doc_root,
                                     routes=routes)
httpd.start(block=True)
