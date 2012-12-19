# elCliente: Base class for all elComandante clients
#
# The class presents an interface to elComandante that all possible
# agents (el_agente) that supervise clients have to implement.

class el_agente():
	def __init__(self, timestamp, log, sclient):
		self.timestamp = timestamp
		self.log = log
		self.sclient = sclient
		self.active = 0
		self.pending = False
		self.name = "el_agente"
		self.subscription = "/el_agente"
	def setup_configuration(self, conf):
		return True
	def setup_initialization(self, init):
		return True
	def check_logfiles_presence(self):
		# Returns a list of logfiles present in the filesystem
		return []
	def check_client_running(self):
		# Check whether a client process is running
		return False
	def start_client(self, timestamp):
		# Start a client process
		return False
	def subscribe(self):
		raise Exception("not implemented")
	def check_subscription(self):
		# Verify the subsystem connection
		return False
	def request_client_exit(self):
		# Request the client to exit with a command
		# through subsystem
		return False
	def kill_client(self):
		# Kill a client with a SIGTERM signal
		return False
	def prepare_test(self, test, environment):
		# Run before a test is executed
		return False
	def execute_test(self, test, environment):
		# Initiate a test
		return False
	def cleanup_test(self, test, environment):
		# Run after a test has executed
		return False
	def final_test_cleanup(self):
		# Cleanup after all tests have finished to return
		# everything to the state before the test
		return False
	def check_finished(self):
		# Check whether the client has finished its task
		# but also check for errors and raise an exception
		# if one occurs.
		return not self.pending
