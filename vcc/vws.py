import requests

from sshtunnel import SSHTunnelForwarder
from urllib.parse import urljoin

from vcc import make_object, settings, signature, json_encoder, VCCError


# Class to connect to VCC Web Service VWS
class VWSclient:
    def __init__(self, config, group_id, keep_alive=False):
        self.tunnel, self.session, self.base_url, self.jwt_data = None, None, None, None
        # Copy elements of web_service into VWSclient class
        self._config, self.group_id, self.keep_alive = config, group_id, keep_alive

        self.connect()

    # Enter function when 'with' is used
    def __enter__(self):
        return self

    # Exit function when 'with' is used
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # Make sure tunnel is close when instance is destroyed
    def __del__(self):
        self.close()

    # Get config for this client
    @property
    def config(self):
        return self._config.__dict__

    # Connect to VCC
    def connect(self):
        url, port = self._config.url, self._config.api_port
        if hasattr(self._config, 'tunnel'):
            self.tunnel = SSHTunnelForwarder(self._config.url, ssh_username=self._config.tunnel,
                                             ssh_pkey=self._config.ssh_pkey,
                                             remote_bind_address=('localhost', port)
                                             )
            self.tunnel.daemon_forward_servers = True
            self.tunnel.start()
            url, port = '127.0.0.1', self.tunnel.local_bind_port

        self.base_url = f'{self._config.protocol}://{url}:{port}'
        self.session = requests.Session()
        self.session.headers.update(signature.make(self.group_id))

    @property
    # Check if site is available by requesting a welcome message
    def is_available(self):
        return self.welcome()

    # Close all connection
    def close(self):
        try:
            if self.session:
                self.session.close()
            self.session = None
            if self.tunnel:
                self.tunnel.stop()
            self.tunnel = None
        except Exception as exc:
            print('Close failed', str(exc))
        finally:
            return

    # Check if web service is returning the welcome message
    def welcome(self):
        rsp = self.get('/', timeout=5)  # Not more than 5 seconds to look for web service
        if rsp: # Not more than 5 seconds to look for web service
            return 'Welcome to VLBI Coordinations Center' in rsp.text
        return False

    # GET data from web service
    def get(self, path, params=None, headers=None, timeout=None, retries=0):
        try:
            rsp = self.session.get(url=urljoin(self.base_url, path), params=params, headers=headers, timeout=timeout)
            self.jwt_data = signature.validate(rsp) if rsp and path != '/' else None
            return rsp
        except requests.exceptions.ConnectionError:
            if self.session and self.keep_alive and retries < 3:
                self.connect()
                return self.get(path, params=params, headers=headers, timeout=timeout, retries=retries+1)
        return None

    # POST data to web service
    def post(self, path, data=None, files=None, headers=None, retries=0):
        try:
            rsp = self.session.post(url=urljoin(self.base_url, path), json=json_encoder(data), files=files,
                                    headers=headers)
            self.jwt_data = signature.validate(rsp) if rsp else None
            return rsp
        except requests.exceptions.ConnectionError:
            if self.session and self.keep_alive and retries < 3:
                self.connect()
                return self.post(path, data=data, files=files, headers=headers, retries=retries+1)
        return None

    # PUT data to web service
    def put(self, path, data=None, files=None, headers=None, retries=0):
        try:
            rsp = self.session.put(url=urljoin(self.base_url, path), json=json_encoder(data), files=files,
                                   headers=headers)
            self.jwt_data = signature.validate(rsp) if rsp else None
            return rsp
        except requests.exceptions.ConnectionError:
            if self.session and self.keep_alive and retries < 3:
                self.connect()
                return self.put(path, data=data, files=files, headers=headers, retries=retries + 1)
        return None

    # DELETE data from web service
    def delete(self, path, headers=None, retries=0):
        try:
            rsp = self.session.delete(url=urljoin(self.base_url, path), headers=headers)
            self.jwt_data = signature.validate(rsp) if rsp else None
            return rsp
        except requests.exceptions.ConnectionError:
            if self.session and self.keep_alive and retries < 3:
                self.connect()
                return self.delete(path, headers=headers, retries=retries + 1)
        return None

    # Get credentials from VCC api to access inbox
    def get_inbox_credentials(self, session=None):
        # Connect to VCC to get username and password to connect to message broker
        try:
            rsp = self.get('/users/inbox', headers={'session': session})
            if rsp:  # Combined client config with information in signature
                return make_object(dict(**self.config, **self.jwt_data))
            raise VCCError(f'Problem at VCC api [{rsp.status_code}] [{rsp.text}]')
        except VCCError as exc:
            raise VCCError(str(exc))


# Get first available VWS client
def get_client(group_id, keep_alive=False):
    # Get list of VLBI Communications Center (VCC)
    if hasattr(settings, 'VCC'):
        for name, config in settings.VCC.__dict__.items():
            setattr(config, 'ssh_pkey', settings.KEY)
            client = VWSclient(config, group_id, keep_alive=keep_alive)
            if client and client.is_available:
                return client
    raise VCCError('could not connect to VCC api')
