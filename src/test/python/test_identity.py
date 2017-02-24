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

import pytest
from covata.delta import Identity


@pytest.fixture(scope="function")
def client(mocker):
    return mocker.MagicMock()


@pytest.fixture(scope="function")
def identity_a(client):
    return Identity(parent=client,
                    id="id-a",
                    public_encryption_key="key-a",
                    external_id="ext-a",
                    metadata=dict(name="a"))


@pytest.fixture(scope="function")
def identity_b(client):
    return Identity(parent=client,
                    id="id-b",
                    public_encryption_key="key-b",
                    external_id="ext-b",
                    metadata=dict(name="b"))


@pytest.mark.parametrize("id_to_retrieve", [None, "other_identity_id"])
def test_get_identity(identity_a, id_to_retrieve, client):
    identity_a.get_identity(id_to_retrieve)
    client.get_identity.assert_called_with(identity_a.id, id_to_retrieve)


@pytest.mark.parametrize("metadata", [{}, dict(name="Bob")])
@pytest.mark.parametrize("page", [None, 1])
@pytest.mark.parametrize("page_size", [None, 5])
def test_get_identities_by_metadata(identity_a, metadata, page, page_size,
                                    client):
    identity_a.get_identities_by_metadata(metadata, page, page_size)
    client.get_identities_by_metadata.assert_called_with(
        identity_a.id, metadata, page, page_size)


def test_repr(identity_a, identity_b):
    assert str(identity_a) == "Identity(id={})".format(identity_a.id)
    assert str(identity_b) == "Identity(id={})".format(identity_b.id)
