
import shutil

from base64 import b64encode
from wsgi_intercept import httplib2_intercept
import wsgi_intercept
import httplib2

from urllib import urlencode
from simplejson import dumps

from tiddlyweb.config import config
from tiddlyweb.web import serve
from tiddlywebplugins.utils import get_store

from tiddlyweb.model.bag import Bag
from tiddlyweb.model.tiddler import Tiddler
from tiddlyweb.model.user import User

def setup_module(module):
    try:
        shutil.rmtree('store')
    except:
        pass

    def app():
        return serve.load_app()
    httplib2_intercept.install()
    wsgi_intercept.add_wsgi_intercept('0.0.0.0', 8080, app)
    wsgi_intercept.add_wsgi_intercept('a.0.0.0.0', 8080, app)
    wsgi_intercept.add_wsgi_intercept('b.0.0.0.0', 8080, app)

    module.store = get_store(config)
    module.http = httplib2.Http()
    user = User('cdent')
    user.set_password('cowpoo')
    store.put(user)

    module.authorization = b64encode('cdent:cowpoo')

    bag = Bag('ho')
    bag.policy.read = ['cdent']
    store.put(bag)
    tiddler = Tiddler('junk', 'ho')
    tiddler.text = 'i am unique'
    store.put(tiddler)


def test_basic_tiddler():
    response, content = http.request(
            'http://a.0.0.0.0:8080/bags/ho/tiddlers/junk.txt')
    assert response['status'] == '401'

    post_data = {'uri': 'http://a.0.0.0.0:8080/bags/ho/tiddlers/junk.txt'}
    post_body = urlencode(post_data)
    response, content = http.request('http://a.0.0.0.0:8080/_',
            method='POST',
            headers={'Content-type': 'application/x-www-form-urlencoded',
                'Authorization': 'Basic %s' % authorization},
            body=post_body)
    assert response['status'] == '201', content
    location = response['location']
    assert 'http://a.0.0.0.0:8080/_/' in location

    response, content = http.request(location)
    assert response['status'] == '200', content
    assert 'i am unique' in content

    response, content = http.request(location, method='PUT')
    assert response['status'] == '405'

    response, content = http.request('http://a.0.0.0.0:8080/_/nonono')
    assert response['status'] == '404'


def test_with_query():
    post_data ={'uri': 'http://b.0.0.0.0:8080/bags/ho/tiddlers?select=title:junk'}
    post_body = dumps(post_data)
    response, content = http.request('http://a.0.0.0.0:8080/_',
            method='POST',
            headers={'Content-type': 'application/json',
                'Authorization': 'Basic %s' % authorization},
            body=post_body)
    assert response['status'] == '201', content
    location = response['location']
    assert 'http://a.0.0.0.0:8080/_/' in location

    response, content = http.request(location)
    assert response['status'] == '200'
    assert 'junk' in content
