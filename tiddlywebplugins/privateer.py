"""
A TiddlyWeb plugin for providing unauthed access to private resources
using "unguessable" URIs.

A URI at a uuid provides an id for a mapping to another URI, internal
to the tiddlyweb server, with the active user being "faked".

This works out okay because:
* only GET is supported
* there's no state that gets carried to the next request

Tiddlers in a bag called PRIVATEER are used to maintain the mappings.
The title of the tiddler is the uuid. The tiddler has two fields:

* uri: the mapped to uri
* user: the user to proxy the action as

An authenticated user can create a new mapping by making a POST
to /_ as either a JSON dictionary with a 'uri' key, or a CGI form
with a uri parameter.

URIs are not checked, you can store what you like and the system
will happily do the internal redirect to it. If junk is stored, a
404 will result.

An authenticated user can list their own mappings by doing a GET to
/_. A JSON dictionary of mappings to uris is returned. Only those
mappings which have a user that matches the currently active user
will be shown.

A user can delete a mapping by sending DELETE to the URI.

Copyright 2010 Chris Dent <cdent@peemore.com>

Licensed as TiddlyWeb, using the BSD License.
"""

__version__ = '0.5'

import simplejson
import urlparse
import uuid

from tiddlyweb.control import filter_tiddlers
from tiddlyweb.model.bag import Bag
from tiddlyweb.model.tiddler import Tiddler
from tiddlyweb.model.user import User
from tiddlyweb.store import StoreError
from tiddlyweb.web.http import HTTP404, HTTP400
from tiddlyweb.web.query import Query
from tiddlyweb.web.negotiate import figure_type
from tiddlyweb.web.util import server_base_url

from tiddlywebplugins.utils import require_any_user, ensure_bag

MAPPING_BAG = 'PRIVATEER'
POLICY = dict(read=['NONE'], write=['NONE'], create=['NONE'],
        manage=['NONE'], accept=['NONE'])


def init(config):
    """
    Install selector routes.
    """
    if 'selector' in config:
        config['selector'].add('/_/{identifier:segment}',
                GET=map_to_private, DELETE=delete_mapping)
        config['selector'].add('/_', GET=mapping_list,
                POST=make_mapping)


@require_any_user()
def delete_mapping(environ, start_response):
    """
    Delete an existing mapping if:
    * the mapping exists
    * the current user and the user in the mapping are the same
    """
    identifier = environ['wsgiorg.routing_args'][1]['identifier']
    current_user = environ['tiddlyweb.usersign']['name']
    store = environ['tiddlyweb.store']

    try:
        tiddler = Tiddler(identifier, MAPPING_BAG)
        tiddler = store.get(tiddler)
        tiddler_user = tiddler.fields['user']
        if current_user != tiddler_user:
            raise HTTP404('resource unavailable')  # obscure user mismatch
        store.delete(tiddler)
    except StoreError:
        raise HTTP404('resource not found')

    start_response('204 No Content', [])
    return []


@require_any_user()
def make_mapping(environ, start_response):
    """
    Establishing a mapping, storing the provided URI
    as a field on a tiddler in the PRIVATEER bag.
    Accepted data is either a json dictory with a uri
    key or a POST CGI form with a uri query paramter.

    Respond with a location header containing the uri
    of the mapping.
    """
    uri = None
    try:
        content_type = environ['tiddlyweb.type']
    except KeyError:
        content_type = None
    if content_type == 'application/json':
        try:
            length = environ['CONTENT_LENGTH']
            content = environ['wsgi.input'].read(int(length))
            data = simplejson.loads(content)
            uri = data['uri']
        except (KeyError, IOError, simplejson.JSONDecodeError), exc:
            raise HTTP400('Unable to parse input: %s' % exc)
    else:
        try:
            uri = environ['tiddlyweb.query']['uri'][0]
        except (KeyError, IndexError), exc:
            raise HTTP400('Unable to parse input: %s' % exc)

    if uri:
        title_uuid = _make_mapping_tiddler(environ, uri)
    else:
        raise HTTP400('No uri for mapping provided')

    start_response('201 Created', [
        ('Location', _mapping_uri(environ, title_uuid))])
    return []


@require_any_user()
def mapping_list(environ, start_response):
    """
    List the mappings for the current user as a JSON
    dictionary: mapping uri -> mapped uri.

    Matching is done based on the user field of the tiddlers
    in the PRIVATEER bag.
    """
    current_user = environ['tiddlyweb.usersign']['name']
    store = environ['tiddlyweb.store']
    try:
        bag = Bag(MAPPING_BAG)
        tiddlers = filter_tiddlers(store.list_bag_tiddlers(bag),
                'select=user:%s' % current_user, environ=environ)
        results = {}
        for tiddler in tiddlers:
            tiddler = store.get(tiddler)
            results[_mapping_uri(environ,
                tiddler.title)] = tiddler.fields['uri']
    except StoreError, exc:
        raise HTTP404('Unable to list mappings: %s' % exc)

    output = simplejson.dumps(results)

    start_response('200 OK', [
        ('Content-Type', 'application/json')])
    return [output]


def map_to_private(environ, start_response):
    """
    Internally redirect a mapping uri to the mapped uri.

    This is done by supplying the mapped uri to the selector
    application for dispatch, but first redoing Query and Negotiate
    handling so that query parameters and content negotiation apply
    based on the mapped uri, not from the mapping uri.
    """
    identifier = environ['wsgiorg.routing_args'][1]['identifier']
    host, target_uri, user = _map_to_uri(environ, identifier)
    environ['tiddlyweb.usersign'] = _proxy_user(environ, user)
    try:
        target_uri, query_string = target_uri.split('?', 1)
        environ['QUERY_STRING'] = query_string.encode('utf-8')
    except ValueError:  # no ?
        pass
    if host:
        environ['HTTP_HOST'] = host.encode('utf-8')
    environ['PATH_INFO'] = target_uri.encode('utf-8')
    environ['SCRIPT_NAME'] = ''
    # reparse the query string into tiddlyweb.query and filters
    Query(None).extract_query(environ)
    figure_type(environ)
    return environ['tiddlyweb.config']['selector'](environ, start_response)


def _make_mapping_tiddler(environ, uri):
    """
    Create and store the tiddler that will persist the mapping.
    """
    store = environ['tiddlyweb.store']
    try:
        mapping_bag = ensure_bag(MAPPING_BAG, store, policy_dict=POLICY)
        title_uuid = '%s' % uuid.uuid4()
        tiddler = Tiddler(title_uuid, mapping_bag.name)
        tiddler.fields['uri'] = uri
        tiddler.fields['user'] = environ['tiddlyweb.usersign']['name']
        store.put(tiddler)
    except StoreError, exc:
        raise HTTP400('Unable to create mapping: %s' % exc)
    return title_uuid


def _map_to_uri(environ, identifier):
    """
    Get host, path and user information about of the mapping tiddler.

    Host is pulled out separately so that we can use virtualhosting
    correctly, if necessary.
    """
    store = environ['tiddlyweb.store']
    try:
        tiddler = Tiddler(identifier, MAPPING_BAG)
        tiddler = store.get(tiddler)
        uri = tiddler.fields['uri']
        user = tiddler.fields['user']
        scheme, netloc, path, params, query, fragment = urlparse.urlparse(uri)
        host = netloc
        path = urlparse.urlunparse(('', '', path, params, query, fragment))
        return host, path, user
    except (StoreError, KeyError), exc:
        raise HTTP404('valid mapping not found: %s' % exc)


def _mapping_uri(environ, identifier):
    """
    The full URI of a mapping uri.
    """
    location = '%s/_/%s' % (server_base_url(environ), identifier)
    return location


def _proxy_user(environ, username):
    """
    Load up the correct user information for the user being proxied
    in a mapping.
    """
    store = environ['tiddlyweb.store']
    try:
        user = User(username)
        user = store.get(user)
        return {'name': user.usersign, 'roles': user.list_roles()}
    except StoreError, exc:
        raise HTTP400('invalid mapping: %s' % exc)
