"""
Tests for mimic identity :mod:`mimic.rest.identity_api`
"""

from __future__ import absolute_import, division, unicode_literals

import json
import uuid

import ddt
from six import text_type

from twisted.trial.unittest import SynchronousTestCase
from twisted.internet.task import Clock

from mimic.core import MimicCore
from mimic.resource import MimicRoot
from mimic.test.dummy import make_example_external_api, ExternalApiStore
from mimic.test.helpers import json_request, request


@ddt.ddt
class TestIdentityMimicOSKSCatalogAdminListExternalServices(SynchronousTestCase):
    """
    Tests for ``/identity/v2.0/services``, provided by
    :obj:`mimic.rest.idenity_api.IdentityApi`
    """
    def setUp(self):
        self.core = MimicCore(Clock(), [])
        self.root = MimicRoot(self.core).app.resource()
        self.uri = "/identity/v2.0/services"
        self.eeapi_name = u"externalServiceName"
        self.headers = {
            b'X-Auth-Token': [b'ABCDEF987654321']
        }
        self.verb = b"GET"

    def test_auth_fail(self):
        """
        GET with no X-Auth-Token header results in 401.
        """
        (response, json_body) = self.successResultOf(
            json_request(self, self.root, self.verb,
                         self.uri))

        self.assertEqual(response.code, 401)
        self.assertEqual(json_body['unauthorized']['code'], 401)

    @ddt.data(
        0, 1, 10
    )
    def test_listing(self, api_entry_count):
        """
        GET will list the registered services.
        """
        api_list = []

        # create the desired number of services per test parameter
        for _ in range(api_entry_count):
            api_list.append(
                ExternalApiStore(
                    text_type(uuid.uuid4()),
                    self.eeapi_name + text_type(uuid.uuid4()),
                    'service-' + text_type(uuid.uuid4()),
                )
            )

        # add the services
        for api in api_list:
            self.core.add_api(api)

        # retrieve the listing using the REST interface
        (response, json_body) = self.successResultOf(
            json_request(self, self.root, self.verb,
                         self.uri,
                         headers=self.headers))

        def validate_api(api_id, api_type, api_name):
            """
            Lookup the API in the test's set of APIs  and match the values
            """
            for api in api_list:
                if api.uuid_key == api_id:
                    # service found, check values and return
                    self.assertEqual(api_id, api.uuid_key)
                    self.assertEqual(api_type, api.type_key)
                    self.assertEqual(api_name, api.name_key)
                    return

            # no service found, raise assertion error
            self.assertFalse(
                True,
                "Unknown service: {0} - {1} - {2}".format(
                    api_id, api_type, api_name))

        self.assertEqual(response.code, 200)
        self.assertEqual(len(json_body["OS-KSADM:services"]), len(api_list))
        # ensure all services in the response match one in the generated
        # initially generated set
        for entry in json_body["OS-KSADM:services"]:
            validate_api(entry['id'], entry['type'], entry['name'])


@ddt.ddt
class TestIdentityMimicOSKSCatalogAdminCreateExternalService(SynchronousTestCase):
    """
    Tests for ``/identity/v2.0/services``, provided by
    :obj:`mimic.rest.idenity_api.IdentityApi`
    """
    def setUp(self):
        self.core = MimicCore(Clock(), [])
        self.root = MimicRoot(self.core).app.resource()
        self.uri = "/identity/v2.0/services"
        self.eeapi_name = u"externalServiceName"
        self.eeapi = make_example_external_api(
            self,
            name=self.eeapi_name,
            set_enabled=True
        )
        self.headers = {
            b'X-Auth-Token': [b'ABCDEF987654321']
        }
        self.verb = b"POST"

    def test_auth_fail(self):
        """
        POST with no X-Auth-Token header results in 401.
        """
        (response, json_body) = self.successResultOf(
            json_request(self, self.root, self.verb,
                         self.uri))

        self.assertEqual(response.code, 401)
        self.assertEqual(json_body['unauthorized']['code'], 401)

    def test_invalid_json_body(self):
        """
        POST will generate 400 when an invalid JSON body is provided.
        """
        (response, json_body) = self.successResultOf(
            json_request(self, self.root, self.verb,
                         self.uri,
                         body=b'<xml>ensure json failure',
                         headers=self.headers))

        self.assertEqual(response.code, 400)
        self.assertEqual(json_body['badRequest']['code'], 400)
        self.assertEqual(json_body['badRequest']['message'],
                         'Invalid JSON request body')

    @ddt.data(
        'type', 'name'
    )
    def test_json_body_missing_required_field(self, remove_field):
        """
        POST requires 'name' field otherwise 400 is generated.
        """
        # normal JSON body
        data = {
            'type': 'some-type',
            'name': 'some-name'
        }
        # remove a portion of the body per the DDT data
        del data[remove_field]

        # POST the resulting JSON to the REST API
        (response, json_body) = self.successResultOf(
            json_request(self, self.root, self.verb,
                         self.uri,
                         body=data,
                         headers=self.headers))

        # API should return 400 since a required field is missing
        self.assertEqual(response.code, 400)
        self.assertEqual(json_body['badRequest']['code'], 400)
        self.assertEqual(json_body['badRequest']['message'],
                         "Invalid Content. 'name' and 'type' fields are "
                         "required.")

    def test_service_uuid_already_exists(self):
        """
        POST requires a unique UUID for the Service ID.
        """
        self.core.add_api(self.eeapi)
        data = {
            'id': self.eeapi.uuid_key,
            'name': self.eeapi.name_key,
            'type': self.eeapi.type_key
        }
        (response, json_body) = self.successResultOf(
            json_request(self, self.root, self.verb,
                         self.uri,
                         body=data,
                         headers=self.headers))

        self.assertEqual(response.code, 409)
        self.assertEqual(json_body['conflict']['code'], 409)
        self.assertEqual(json_body['conflict']['message'],
                         "Conflict: Service with the same uuid already "
                         "exists.")

    def test_service_name_already_exists(self):
        """
        POST requires a unique name for the service Name.
        """
        self.core.add_api(self.eeapi)
        data = {
            'id': str(uuid.uuid4()),
            'name': self.eeapi.name_key,
            'type': self.eeapi.type_key
        }
        (response, json_body) = self.successResultOf(
            json_request(self, self.root, self.verb,
                         self.uri,
                         body=data,
                         headers=self.headers))

        self.assertEqual(response.code, 409)
        self.assertEqual(json_body['conflict']['code'], 409)
        self.assertEqual(json_body['conflict']['message'],
                         "Conflict: Service with the same name already "
                         "exists.")

    @ddt.data(
        True, False
    )
    def test_successfully_add_service(self, has_id_field):
        """
        POST accepts the service type and name regardless of whether
        an ID field is provided.
        """
        data = {
            'name': self.eeapi.name_key,
            'type': self.eeapi.type_key,
            'id': text_type(uuid.uuid4())
        }
        if not has_id_field:
            del data['id']

        req = request(self, self.root, self.verb,
                      "/identity/v2.0/services",
                      body=json.dumps(data).encode("utf-8"),
                      headers=self.headers)

        response = self.successResultOf(req)
        self.assertEqual(response.code, 201)

    def test_successfully_add_service_with_description(self):
        """
        POST accepts a Service Description.
        """
        data = {
            'name': self.eeapi.name_key,
            'type': self.eeapi.type_key,
            'description': 'testing external API'
        }
        req = request(self, self.root, self.verb,
                      self.uri,
                      body=json.dumps(data).encode("utf-8"),
                      headers=self.headers)

        response = self.successResultOf(req)
        self.assertEqual(response.code, 201)


class TestIdentityMimicOSKSCatalogAdminDeleteExternalService(SynchronousTestCase):
    """
    Tests for ``/identity/v2.0/services/<service-id>``, provided by
    :obj:`mimic.rest.idenity_api.IdentityApi`
    """
    def setUp(self):
        self.core = MimicCore(Clock(), [])
        self.root = MimicRoot(self.core).app.resource()
        self.eeapi_id = u"some-id"
        self.uri = "/identity/v2.0/services/" + self.eeapi_id
        self.eeapi_name = u"externalServiceName"
        self.eeapi = make_example_external_api(
            self,
            name=self.eeapi_name,
            set_enabled=True
        )
        self.eeapi2 = make_example_external_api(
            self,
            name=self.eeapi_name + " alternate"
        )
        self.eeapi.uuid_key = self.eeapi_id
        self.headers = {
            b'X-Auth-Token': [b'ABCDEF987654321']
        }
        self.verb = b"DELETE"

    def test_auth_fail(self):
        """
        DELETE with no X-Auth-Token header results in 401.
        """
        (response, json_body) = self.successResultOf(
            json_request(self, self.root, self.verb,
                         self.uri))

        self.assertEqual(response.code, 401)
        self.assertEqual(json_body['unauthorized']['code'], 401)

    def test_invalid_service(self):
        """
        DELETE an unknown service will generate a 404.
        """
        data = {
            'name': 'some-name',
            'type': 'some-type',
            'id': 'some-id'
        }
        (response, json_body) = self.successResultOf(
            json_request(self, self.root, self.verb,
                         self.uri,
                         body=data,
                         headers=self.headers))

        self.assertEqual(response.code, 404)
        self.assertEqual(json_body['itemNotFound']['code'], 404)
        self.assertEqual(json_body['itemNotFound']['message'],
                         "Service not found. Unable to remove.")

    def test_service_has_template(self):
        """
        DELETE a service that still has a template results in 409.
        """
        self.core.add_api(self.eeapi)
        data = {
            'name': self.eeapi.name_key,
            'type': self.eeapi.type_key,
            'id': self.eeapi.uuid_key
        }
        (response, json_body) = self.successResultOf(
            json_request(self, self.root, self.verb,
                         self.uri,
                         body=data,
                         headers=self.headers))

        self.assertEqual(response.code, 409)
        self.assertEqual(json_body['conflict']['code'], 409)
        self.assertEqual(json_body['conflict']['message'],
                         "Service still has endpoint templates.")

    def test_remove_service(self):
        """
        DELETE a service.
        """
        templates_to_remove = list(self.eeapi.endpoint_templates.keys())
        for template_id in templates_to_remove:
            self.eeapi.remove_template(template_id)

        self.core.add_api(self.eeapi)
        self.core.add_api(self.eeapi2)
        data = {
            'name': self.eeapi.name_key,
            'type': self.eeapi.type_key,
            'id': self.eeapi.uuid_key
        }

        req = request(self, self.root, self.verb,
                      self.uri,
                      body=json.dumps(data).encode("utf-8"),
                      headers=self.headers)

        response = self.successResultOf(req)
        self.assertEqual(response.code, 204)
