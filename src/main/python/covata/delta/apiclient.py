#   Copyright 2017 Covata Limited or its affiliates
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from __future__ import absolute_import

import requests

from . import signer, utils

from enum import Enum


class SecretLookupType(Enum):
    """
    Enumerates the applicable secret lookup types.
    """
    base = 1
    """
    Restricts lookup to base secrets.
    """

    derived = 2
    """
    Restricts lookup to derived secrets.
    """

    any = 3
    """
    Perform lookup on both base and derived secrets.
    """


class ApiClient:
    """
    The Delta API Client is an abstraction over the Delta API for execution of
    requests and responses.
    """

    DELTA_URL = 'https://delta.covata.io/v1'        # type: str
    RESOURCE_IDENTITIES = '/identities'             # type: str
    RESOURCE_SECRETS = '/secrets'                   # type: str
    RESOURCE_EVENTS = '/events'                     # type: str

    def __init__(self, key_store):
        """
        Constructs a new Delta API client with the given configuration.

        :param key_store: the DeltaKeyStore object
        :type key_store: :class:`DeltaKeyStore`
        """
        self.__key_store = key_store

    @property
    def key_store(self):
        return self.__key_store

    def register_identity(self, public_encryption_key, public_signing_key,
                          external_id=None, metadata=None):
        """
        Creates a new identity in Delta with the provided metadata
        and external id.

        :param str public_encryption_key:
            the public encryption key to associate with the identity
        :param str public_signing_key:
            the public signing key to associate with the identity
        :param external_id: the external id to associate with the identity
        :type external_id: str | None
        :param metadata: the metadata to associate with the identity
        :type metadata: dict[str, str] | None
        :return: the id of the newly created identity
        :rtype: str
        """
        body = dict(
            signingPublicKey=public_signing_key,
            cryptoPublicKey=public_encryption_key,
            externalId=external_id,
            metadata=metadata)

        response = requests.post(
            url=self.DELTA_URL + self.RESOURCE_IDENTITIES,
            json=dict((k, v) for k, v in body.items() if v is not None))
        response.raise_for_status()
        identity_id = response.json()['identityId']

        return identity_id

    @utils.check_id("requestor_id, identity_id")
    def get_identity(self, requestor_id, identity_id):
        """
        Gets the identity matching the given identity id.

        :param str requestor_id: the authenticating identity id
        :param str identity_id: the identity id to retrieve
        :return: the retrieved identity
        :rtype: dict[str, any]
        """
        response = requests.get(
            url="{base_url}{resource}/{identity_id}".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_IDENTITIES,
                identity_id=identity_id),
            auth=self.signer(requestor_id))
        response.raise_for_status()
        identity = response.json()
        return identity

    @utils.check_id("requestor_id")
    @utils.check_optional_pagination("page, page_size")
    @utils.check_arguments(
        "metadata",
        lambda x: x is not None and dict(x),
        "must be a non-empty dict[str, str]")
    def get_identities_by_metadata(self, requestor_id, metadata,
                                   page=None, page_size=None):
        """
        Gets a list of identities matching the given metadata key and value
        pairs, bound by the pagination parameters.

        :param str requestor_id: the authenticating identity id
        :param metadata: the metadata key and value pairs to filter
        :type metadata: dict[str, str]
        :param page: the page number
        :type page: int | None
        :param page_size: the page size
        :type page_size: int | None
        :return: a list of identities satisfying the request
        :rtype: list[dict[str, any]]
        """
        metadata_ = dict(("metadata." + k, v) for k, v in metadata.items())
        response = requests.get(
            url="{base_url}{resource}".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_IDENTITIES),
            params=dict(metadata_,
                        page=int(page) if page else None,
                        pageSize=int(page_size) if page_size else None),
            auth=self.signer(requestor_id))
        response.raise_for_status()
        return response.json()

    @utils.check_id("requestor_id")
    def create_secret(self, requestor_id, content, encryption_details):
        """
        Creates a new secret in Delta. The key used for encryption should
        be encrypted with the key of the authenticating identity.

        It is the responsibility of the caller to ensure that the contents
        and key material in the encryption details are properly represented
        in a suitable string encoding (such as base64).

        :param str requestor_id: the authenticating identity id
        :param str content: the contents of the secret
        :param encryption_details: the encryption details
        :type encryption_details: dict[str, str]
        :return: the created base secret
        :rtype: dict[str, str]
        """
        response = requests.post(
            url="{base_url}{resource}".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_SECRETS),
            json=dict(
                content=content,
                encryptionDetails=encryption_details
            ),
            auth=self.signer(requestor_id))

        response.raise_for_status()
        return response.json()

    @utils.check_id("requestor_id, base_secret_id, rsa_key_owner_id")
    def share_secret(self, requestor_id, content, encryption_details,
                     base_secret_id, rsa_key_owner_id):
        """
        Shares the base secret with the specified target RSA key owner. The
        contents must be encrypted with the public encryption key of the
        RSA key owner, and the encrypted key and initialisation vector must
        be provided. This call will result in a new derived secret being created
        and returned as a response.

        It is the responsibility of the caller to ensure that the contents
        and key material in the encryption details are properly represented
        in a suitable string encoding (such as base64).

        :param str requestor_id: the authenticating identity id
        :param str content: the contents of the secret
        :param encryption_details: the encryption details
        :type encryption_details: dict[str, str]
        :param str base_secret_id: the id of the base secret
        :param str rsa_key_owner_id: the id of the rsa key owner
        :return: the created derived secret
        :rtype: dict[str, str]
        """
        response = requests.post(
            url="{base_url}{resource}".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_SECRETS),
            json=dict(
                content=content,
                encryptionDetails=encryption_details,
                baseSecret=base_secret_id,
                rsaKeyOwner=rsa_key_owner_id
            ),
            auth=self.signer(requestor_id))

        response.raise_for_status()
        return response.json()

    @utils.check_id("requestor_id, secret_id")
    def delete_secret(self, requestor_id, secret_id):
        """
        Deletes the secret with the given secret id.

        :param str requestor_id: the authenticating identity id
        :param str secret_id: the secret id to be deleted
        """
        response = requests.delete(
            url="{base_url}{resource}/{secret_id}".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_SECRETS,
                secret_id=secret_id),
            auth=self.signer(requestor_id))
        response.raise_for_status()

    @utils.check_id("requestor_id, secret_id")
    def get_secret(self, requestor_id, secret_id):
        """
        Gets the given secret. This does not include the metadata and contents,
        they need to be made as separate requests,
        :func:`~.ApiClient.get_secret_metadata`
        and :func:`~.ApiClient.get_secret_content` respectively.

        :param str requestor_id: the authenticating identity id
        :param str secret_id: the secret id to be retrieved
        :return: the retrieved secret
        :rtype: dict[str, any]
        """
        response = requests.get(
            url="{base_url}{resource}/{secret_id}".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_SECRETS,
                secret_id=secret_id),
            auth=self.signer(requestor_id))
        response.raise_for_status()
        return response.json()

    @utils.check_id("requestor_id, secret_id")
    def get_secret_metadata(self, requestor_id, secret_id):
        """
        Gets the metadata key and value pairs for the given secret.

        :param str requestor_id: the authenticating identity id
        :param str secret_id: the secret id to be retrieved
        :return: the retrieved secret metadata dictionary and version tuple
        :rtype: (dict[str, str], int)
        """
        response = requests.get(
            url="{base_url}{resource}/{secret_id}/metadata".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_SECRETS,
                secret_id=secret_id),
            auth=self.signer(requestor_id))

        response.raise_for_status()
        metadata = dict(response.json())
        version = int(response.headers["ETag"])
        return metadata, version

    @utils.check_id("requestor_id, secret_id")
    def get_secret_content(self, requestor_id, secret_id):
        """
        Gets the contents of the given secret.

        :param str requestor_id: the authenticating identity id
        :param str secret_id: the secret id to be retrieved
        :return: the retrieved secret
        :rtype: str
        """
        response = requests.get(
            url="{base_url}{resource}/{secret_id}/content".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_SECRETS,
                secret_id=secret_id),
            auth=self.signer(requestor_id))

        response.raise_for_status()
        return response.text

    @utils.check_id("requestor_id, secret_id")
    @utils.check_metadata("metadata")
    def update_secret_metadata(self,
                               requestor_id,
                               secret_id,
                               metadata,
                               version):
        """
        Updates the metadata of the given secret given the version number.
        The version of a secret's metadata can be obtained by calling
        :func:`~.ApiClient.get_secret`.

        A newly created base secret has a metadata version of 1.

        :param str requestor_id: the authenticating identity id
        :param str secret_id: the secret id to be updated
        :param metadata: metadata dictionary
        :type metadata: dict[str, str]
        :param int version: metadata version, required for optimistic locking
        """
        response = requests.put(
            url="{base_url}{resource}/{secret_id}/metadata".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_SECRETS,
                secret_id=secret_id),
            headers={
                "if-match": str(version)
            },
            json=metadata,
            auth=self.signer(requestor_id))

        response.raise_for_status()

    @utils.check_id("requestor_id, identity_id")
    def update_identity_metadata(self,
                                 requestor_id,
                                 identity_id,
                                 metadata,
                                 version):
        """
        Updates the metadata of the given identity given the version number.
        The version of an identity's metadata can be obtained by calling
        :func:`~.ApiClient.get_identity`.

        An identity has an initial metadata version of 1.

        :param str requestor_id: the authenticating identity id
        :param str identity_id: the identity id to be updated
        :param metadata: metadata dictionary
        :type metadata: dict[str, str]
        :param int version: metadata version, required for optimistic locking
        """
        response = requests.put(
            url="{base_url}{resource}/{identity_id}".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_IDENTITIES,
                identity_id=identity_id),
            headers={
                "if-match": str(version)
            },
            json=dict(metadata=metadata),
            auth=self.signer(requestor_id))
        response.raise_for_status()

    @utils.check_id("requestor_id")
    @utils.check_optional_id("secret_id, rsa_key_owner_id")
    def get_events(self, requestor_id, secret_id=None, rsa_key_owner_id=None):
        """
        Gets a list of events associated filtered by secret id or RSA key owner
        or both secret id and RSA key owner.

        :param str requestor_id: the authenticating identity id
        :param secret_id: the secret id of interest
        :type secret_id: str | None
        :param rsa_key_owner_id: the rsa key owner id of interest
        :type rsa_key_owner_id: str | None
        :return: a list of audit events
        :rtype: list[dict[str, any]]
        """
        params = dict(purpose="AUDIT")
        if secret_id is not None:
            params["secretId"] = str(secret_id)
        if rsa_key_owner_id is not None:
            params["rsaKeyOwner"] = str(rsa_key_owner_id)

        response = requests.get(
            url="{base_url}{resource}".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_EVENTS),
            params=params,
            auth=self.signer(requestor_id))
        response.raise_for_status()
        return response.json()

    @utils.check_id("requestor_id")
    @utils.check_optional_id("base_secret_id, created_by, rsa_key_owner_id")
    @utils.check_optional_pagination("page, page_size")
    @utils.check_arguments(
        "metadata",
        lambda x: x is None or dict(x),
        "must be a non-empty dict[str, str]")
    @utils.check_arguments(
        "lookup_type",
        lambda x: isinstance(x, SecretLookupType),
        "must be an instance of SecretLookupType")
    def get_secrets(self,
                    requestor_id,
                    base_secret_id=None,
                    created_by=None,
                    rsa_key_owner_id=None,
                    metadata=None,
                    lookup_type=SecretLookupType.any,
                    page=None,
                    page_size=None):
        """
        Gets a list of secrets based on the query parameters, bound by the
        pagination parameters.

        :param str requestor_id: the authenticating identity id
        :param base_secret_id: the id of the base secret
        :type base_secret_id: str | None
        :param created_by: the id of the secret creator
        :type created_by: str | None
        :param rsa_key_owner_id: the id of the RSA key owner
        :type rsa_key_owner_id: str | None
        :param metadata: the metadata associated with the secret
        :type metadata: dict[str, str] | None
        :param lookup_type: the type of the lookup query
        :type lookup_type: :class:`~.SecretLookupType`
        :param page: the page number
        :type page: int | None
        :param page_size: the page size
        :type page_size: int | None
        :return:
        """
        params = dict(
            page=int(page) if page else None,
            pageSize=int(page_size) if page_size else None,
            baseSecret=None if base_secret_id is None else str(base_secret_id),
            createdBy=None if created_by is None else str(created_by),
            rsaKeyOwner=None if rsa_key_owner_id is None else str(
                rsa_key_owner_id))

        if metadata is not None:
            metadata_ = dict(("metadata." + k, v) for k, v in metadata.items())
            params.update(metadata_)

        if lookup_type is SecretLookupType.base:
            params["baseSecret"] = "false"
        elif lookup_type is SecretLookupType.derived:
            params["baseSecret"] = "true"

        response = requests.get(
            url="{base_url}{resource}".format(
                base_url=self.DELTA_URL,
                resource=self.RESOURCE_SECRETS),
            params=params,
            auth=self.signer(requestor_id))
        response.raise_for_status()
        return response.json()

    @utils.check_id("identity_id")
    def signer(self, identity_id):
        """
        Generates a request signer function for the
        the authorizing identity.

        >>> signer = api_client.signer(authorizing_identity)

        :param str identity_id: the authorizing identity id
        :return: the request signer function
        :rtype: (:class:`PreparedRequest`) -> :class:`PreparedRequest`
        """
        def sign_request(r):
            # type: (requests.PreparedRequest) -> requests.PreparedRequest
            signing_key = self.key_store.get_private_signing_key(identity_id)
            r.headers = signer.get_updated_headers(
                identity_id=identity_id,
                method=r.method,
                url=r.url,
                headers=r.headers,
                payload=r.body,
                private_signing_key=signing_key)
            return r
        return sign_request
