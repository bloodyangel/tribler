import logging
import logging.config
import os

from twisted.internet.defer import inlineCallbacks

import Tribler.Core.Utilities.json_util as json
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.twisted_thread import deferred
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestCircuitDebugEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestCircuitDebugEndpoint, self).setUp(autoload_discovery=autoload_discovery)

        self.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        self.dispersy._database.open()
        master_member = DummyMember(self.dispersy, 1, "a" * 20)
        member = self.dispersy.get_new_member(u"curve25519")

        self.tunnel_community = HiddenTunnelCommunity(self.dispersy, master_member, member)
        self.dispersy.get_communities = lambda: [self.tunnel_community]
        self.session.get_dispersy_instance = lambda: self.dispersy

    def setUpPreSession(self):
        super(TestCircuitDebugEndpoint, self).setUpPreSession()
        self.config.set_tunnel_community_enabled(True)

    @deferred(timeout=10)
    def test_get_circuit_no_community(self):
        """
        Testing whether the API returns error 404 if no tunnel community is loaded
        """
        self.dispersy.get_communities = lambda: []
        return self.do_request('debug/circuits', expected_code=404)

    @deferred(timeout=10)
    def test_get_circuits(self):
        """
        Testing whether the API returns the correct circuits
        """
        mock_hop = MockObject()
        mock_hop.host = 'somewhere'
        mock_hop.port = 4242

        mock_circuit = MockObject()
        mock_circuit.state = 'TESTSTATE'
        mock_circuit.goal_hops = 42
        mock_circuit.bytes_up = 200
        mock_circuit.bytes_down = 400
        mock_circuit.creation_time = 1234
        mock_circuit.hops = [mock_hop]

        self.tunnel_community.circuits = {'abc': mock_circuit}

        def verify_response(response):
            response_json = json.loads(response)
            self.assertEqual(len(response_json['circuits']), 1)
            self.assertEqual(response_json['circuits'][0]['state'], 'TESTSTATE')
            self.assertEqual(response_json['circuits'][0]['bytes_up'], 200)
            self.assertEqual(response_json['circuits'][0]['bytes_down'], 400)
            self.assertEqual(len(response_json['circuits'][0]['hops']), 1)
            self.assertEqual(response_json['circuits'][0]['hops'][0]['host'], 'somewhere:4242')

        self.should_check_equality = False
        return self.do_request('debug/circuits', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_open_files(self):
        """
        Test whether the API returns open files
        """
        def verify_response(response):
            response_json = json.loads(response)
            self.assertGreaterEqual(len(response_json['open_files']), 1)

        self.should_check_equality = False
        return self.do_request('debug/open_files', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_open_sockets(self):
        """
        Test whether the API returns open sockets
        """

        def verify_response(response):
            response_json = json.loads(response)
            self.assertGreaterEqual(len(response_json['open_sockets']), 1)

        self.should_check_equality = False
        return self.do_request('debug/open_sockets', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_threads(self):
        """
        Test whether the API returns open threads
        """

        def verify_response(response):
            response_json = json.loads(response)
            self.assertGreaterEqual(len(response_json['threads']), 1)

        self.should_check_equality = False
        return self.do_request('debug/threads', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_cpu_history(self):
        """
        Test whether the API returns the cpu history
        """

        def verify_response(response):
            response_json = json.loads(response)
            self.assertGreaterEqual(len(response_json['cpu_history']), 1)

        self.session.lm.resource_monitor.check_resources()
        self.should_check_equality = False
        return self.do_request('debug/cpu/history', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_memory_history(self):
        """
        Test whether the API returns the memory history
        """

        def verify_response(response):
            response_json = json.loads(response)
            self.assertGreaterEqual(len(response_json['memory_history']), 1)

        self.session.lm.resource_monitor.check_resources()
        self.should_check_equality = False
        return self.do_request('debug/memory/history', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_dump_memory(self):
        """
        Test whether the API returns a memory dump
        """

        def verify_response(response):
            self.assertTrue(response)

        self.should_check_equality = False
        return self.do_request('debug/memory/dump', expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_debug_pane_logs(self):
        """
        Test whether the API returns the logs
        """

        test_log_message = "This is the test log message"
        max_lines = 100

        import Tribler
        project_root_dir = os.path.abspath(os.path.join(os.path.dirname(Tribler.__file__), ".."))
        log_config = os.path.join(project_root_dir, "logger.conf")

        # State directory for logs
        state_log_dir = os.path.join(self.session.config.get_state_dir(), 'logs')
        if not os.path.exists(state_log_dir):
            os.makedirs(state_log_dir)

        # Setup logging
        logging.info_log_file = os.path.join(state_log_dir, 'tribler-info.log')
        logging.error_log_file = os.path.join(state_log_dir, 'tribler-error.log')
        logging.config.fileConfig(log_config, disable_existing_loggers=False)

        def verify_log_exists(response):
            json_response = json.loads(response)
            logs = json_response['content'].strip().split("\n")

            # Check number of logs returned is correct
            self.assertEqual(len(logs), max_lines)

            # Check if test log message is present in the logs, at least once
            log_exists = any((True for log in logs if test_log_message in log))
            self.assertTrue(log_exists, "Test log not found in the debug log response")

        # write 100 test logs which is used to test for its presence in the response
        for log_index in xrange(100):
            logging.error("%s [%d]", test_log_message, log_index)

        self.should_check_equality = False
        return self.do_request('debug/log?max_lines=%d' % max_lines, expected_code=200).addCallback(verify_log_exists)
