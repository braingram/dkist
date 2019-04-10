import json
import stat
import pathlib
from unittest import mock

import requests
import globus_sdk

from dkist.utils.globus.auth import (get_cache_contents, get_cache_file_path, save_auth_cache,
                                     start_local_server, get_refresh_token_authorizer)


def test_http_server():
    server = start_local_server()
    redirect_uri = "http://{a[0]}:{a[1]}".format(a=server.server_address)
    inp_code = "wibble"

    requests.get(redirect_uri + f"?code={inp_code}")

    code = server.wait_for_code()

    assert code == inp_code


@mock.patch("appdirs.user_cache_dir", return_value="/tmp/test/")
def test_get_cache_file_path(mock_appdirs):
    path = get_cache_file_path()
    assert isinstance(path, pathlib.Path)

    assert path.parent == pathlib.Path("/tmp/test")
    assert path.name == "globus_auth_cache.json"


def test_get_no_cache(tmpdir):
    with mock.patch("appdirs.user_cache_dir", return_value=str(tmpdir)):
        # Test file not exists
        cache = get_cache_contents()
        assert isinstance(cache, dict)
        assert not cache


def test_get_cache(tmpdir):
    with mock.patch("appdirs.user_cache_dir", return_value=str(tmpdir)):
        with open(tmpdir / "globus_auth_cache.json", "w") as fd:
            json.dump({"hello": "world"}, fd)

        cache = get_cache_contents()
        assert isinstance(cache, dict)
        assert len(cache) == 1
        assert cache == {"hello": "world"}


def test_get_cache_not_json(tmpdir):
    with mock.patch("appdirs.user_cache_dir", return_value=str(tmpdir)):
        with open(tmpdir / "globus_auth_cache.json", "w") as fd:
            fd.write("aslkjdasdjjdlsajdjklasjdj, akldjaskldjasd, lkjasdkljasldkjas")

        cache = get_cache_contents()
        assert isinstance(cache, dict)
        assert not cache


def test_save_auth_cache(tmpdir):
    filename = tmpdir / "globus_auth_cache.json"
    assert not filename.exists()  # Sanity check
    with mock.patch("appdirs.user_cache_dir", return_value=str(tmpdir)):
        save_auth_cache({"hello": "world"})

    assert filename.exists()
    statinfo = filename.stat()

    # Test that the user can read and write
    assert bool(statinfo.mode & stat.S_IRUSR)
    assert bool(statinfo.mode & stat.S_IWUSR)
    # Test that neither "Group" or "Other" have read permissions
    assert not bool(statinfo.mode & stat.S_IRGRP)
    assert not bool(statinfo.mode & stat.S_IROTH)


def test_get_refresh_token_authorizer():
    # An example cache without real tokens
    cache = {
        "transfer.api.globus.org": {
            "scope": "urn:globus:auth:scope:transfer.api.globus.org:all",
            "access_token": "buscVeATmhfB0v1tzu8VmTfFRB1nwlF8bn1R9rQTI3Q",
            "refresh_token": "YSbLZowAHfmhxehUqeOF3lFvoC0FlTT11QGupfWAOX4",
            "token_type": "Bearer",
            "expires_at_seconds": 1553362861,
            "resource_server": "transfer.api.globus.org"
        }
    }

    with mock.patch("dkist.utils.globus.auth.get_cache_contents", return_value=cache):
        auth = get_refresh_token_authorizer()
        assert isinstance(auth, globus_sdk.RefreshTokenAuthorizer)
        assert auth.access_token == cache["transfer.api.globus.org"]["access_token"]

    with mock.patch("dkist.utils.globus.auth.do_native_app_authentication", return_value=cache):
        auth = get_refresh_token_authorizer(force_reauth=True)
        assert isinstance(auth, globus_sdk.RefreshTokenAuthorizer)
        assert auth.access_token == cache["transfer.api.globus.org"]["access_token"]
