"""
Functions for interacting with globus endpoints.
"""
import pathlib
import webbrowser

import globus_sdk

from .auth import get_refresh_token_authorizer


__all__ = ['get_directory_listing']


def get_transfer_client(force_reauth=False):
    """
    Get an authorized transfer client.

    Parameters
    ----------
    force_reauth : `bool`, optional
        Do not use cached authentication details when `True`.

    Returns
    -------
    `globus_sdk.TransferClient`
    """
    return globus_sdk.TransferClient(get_refresh_token_authorizer(force_reauth))


def get_local_endpoint_id():
    """
    Get the endpoint ID of a local Globus Connect Personal endpoint.

    Returns
    -------
    endpoint_id : `str`
        The endpoint ID.

    Raises
    ------
    ConnectionError
        If no local endpoint can be detected a connection error is raised.

    """
    local_endpoint = globus_sdk.LocalGlobusConnectPersonal()
    endpoint_id = local_endpoint.endpoint_id

    if not endpoint_id:
        raise ConnectionError(
            "Can not find a local Globus Connect endpoint.")

    return endpoint_id


def get_endpoint_id(endpoint, tfr_client):
    """
    Resolve an endpoint description to an ID.

    This uses the `endpoint search
    <https://docs.globus.org/api/transfer/endpoint_search/#endpoint_search>`__
    functionality of the Globus API, so any endpoint search can be specified.
    One and only one result must be returned from the search or a `ValueError`
    will be raised.

    Parameters
    ----------
    endpoint : `str`
        A description of an endpoint.

    tfr_client : `globus_sdk.TransferClient`
        The transfer client to use to query the endpoint.

    """
    tr = None

    # If there is a space in the endpoint it's not an id
    if ' ' not in endpoint:
        try:
            tr = tfr_client.get_endpoint(endpoint)
        except globus_sdk.TransferAPIError as e:
            if e.code != "EndpointNotFound":
                raise

    if not tr:
        tr = tfr_client.endpoint_search(endpoint)

    responses = tr.data

    if len(responses) > 1:
        display_names = [a['display_name'] for a in responses]
        # If we have one and only one exact display name match use that
        if display_names.count(endpoint) == 1:
            return responses[display_names.index(endpoint)]['id']
        raise ValueError(f"Multiple matches for endpoint '{endpoint}': {display_names}")

    elif len(responses) == 0:
        raise ValueError(f"No matches found for endpoint '{endpoint}'")

    return responses[0]['id']


def auto_activate_endpoint(tfr_client, endpoint_id):
    """
    Perform activation of a Globus endpoint.

    Parameters
    ----------
    tfr_client : `globus_sdk.TransferClient`
        The transfer client to use for the activation.

    endpoint_id : `str`
        The uuid of the endpoint to activate.

    """
    activation = tfr_client.endpoint_get_activation_requirements(endpoint_id)
    needs_activation = bool(activation['DATA'])
    activated = activation['activated']
    if needs_activation and not activated:
        r = tfr_client.endpoint_autoactivate(endpoint_id)
        if r['code'] == "AutoActivationFailed":
            webbrowser.open(f"https://www.globus.org/app/endpoints/{endpoint_id}/activate",
                            new=1)
            input("Press Return after completing activation in your webbrowser...")
            r = tfr_client.endpoint_autoactivate(endpoint_id)


def get_directory_listing(path, endpoint=None, force_reauth=False):
    """
    Retrieve a list of all files in the path.

    Parameters
    ----------
    path : `pathlib.Path` or `str`
        The path to list on the endpoint.

    endpoint : `str` or `None`
        The name or uuid of the endpoint to use or None to attempt to connect
        to a local endpoint.

    force_reauth : `bool`, optional
        Do not use cached authentication when `True`.

    Returns
    -------
    listing : `tuple`
        A list of all the files.

    """
    path = pathlib.Path(path)

    endpoint_id = None
    if endpoint is None:
        endpoint_id = get_local_endpoint_id()

    # Set this up after attempting local endpoint discovery so that we fail on
    # local endpoint discovery before needing to login.
    tc = get_transfer_client(force_reauth=force_reauth)

    if endpoint_id is None:
        endpoint_id = get_endpoint_id(endpoint, tc)
        auto_activate_endpoint(tc, endpoint_id)

    response = tc.operation_ls(endpoint_id, path=path.as_posix())
    names = [r['name'] for r in response]

    return [path / n for n in names]
