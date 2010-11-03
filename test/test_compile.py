


def test_compile():
    try:
        import tiddlywebplugins.privateer
        assert True
    except ImportError, exc:
        assert False, exc
