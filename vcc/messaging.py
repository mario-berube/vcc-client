import functools

from datetime import datetime, date
from sshtunnel import SSHTunnelForwarder
from urllib.parse import quote

import pika
import json

from vcc import json_encoder


# Define VLBIexception
class RMQclientException(Exception):
    def __init__(self, err_msg):
        self.err_msg = err_msg


# Class to send/receive messages with the message broker of the VCC.
class RMQclient:

    def __init__(self, config, multi=False):
        # Default TTL for important messages
        self.ttl = 5000
        self.max_attempts = 5

        # Initialize some variables
        self.exchange = self.queue = self.tunnel = None
        self._config = config

        self._last_msg = (None, None)
        self.connection, self.publishing, self.consuming = None, None, None
        self.timeout, self.timeout_id = 300, None
        self.process_msg, self.process_timeout = self.do_nothing, None
        self._errors = []
        self.close_requested = False
        if not multi:  # Do not need multithread approach for sending message
            self.send = self._send

    # Implement __enter__
    def __enter__(self):
        self.connect()
        return self

    # Implement __exit__ needed by __enter__
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # Get config for this client
    @property
    def config(self):
        return self._config.__dict__

    # Make sure communications are close when instance is destroyed
    def __del__(self):
        self.close()

    # Catch Ctrl+C
    def signal_handler(self, sig, frame):
        self.close()

    # Add error message to list
    def add_error(self, string):
        self._errors.append(string)

    # Check if any error message
    @property
    def has_error(self):
        return bool(self._errors)

    # Return the list of errors as string
    @property
    def errors(self):
        return '\n'.join(self._errors)

    # Connect to broker
    def connect(self):
        self.connection, self.publishing, self.consuming = None, None, None
        url, port = self._config.url, self._config.msg_port
        self.exchange, self.queue = self._config.exchange, self._config.queue

        try:
            if hasattr(self._config, 'tunnel'):
                try:
                    self.tunnel = SSHTunnelForwarder(url, ssh_username=self._config.tunnel,
                                                     ssh_pkey=self._config.ssh_pkey,
                                                     remote_bind_address=('localhost', port)
                                                     )
                    self.tunnel.start()
                except Exception as exc:
                    raise RMQclientException(f'Could not start tunnel {str(exc)}')
                url, port = '127.0.0.1', self.tunnel.local_bind_port

            user, password = self.config.get('credentials')
            credentials = pika.credentials.PlainCredentials(user, password)
            parameters = pika.ConnectionParameters(host=url, port=int(port), credentials=credentials,
                                                   virtual_host=quote(self.config['vhost'], safe=""))
            self.connection = pika.BlockingConnection(parameters)
        except pika.exceptions.AMQPConnectionError as err:
            self.add_error(f'Could not connect to VCC message broker')
            raise RMQclientException(f'Could not connect {str(err)}')

    # Connect a channel
    def connect_channel(self, channel, name):
        try:
            if not channel or channel.is_closed:
                return self.connection.channel()
            return channel
        except pika.exceptions.AMQPConnectionError as err:
            raise RMQclientException(f'Could not connect to {name} channel {str(err)}')

    # Gracefully stop a connection
    @staticmethod
    def stop_it(item):
        try:
            item.stop()
        finally:
            return None

    @staticmethod
    def close_it(item):
        try:
            item.close()
        finally:
            return None

    # Close all connection
    def close(self):
        self.close_requested = True
        # Close all connections
        [self.close_it(item) for item in [self.publishing, self.consuming, self.connection] if item]
        self.publishing = self.consuming = self.connection = None
        # Stop tunnel
        self.tunnel = self.stop_it(self.tunnel) if self.tunnel else None

    # Thread safe function to send message
    def send(self, sender, code, key, data, reply_to='', priority=0, ttl=None, to_queue=False):
        cb = functools.partial(self._send, sender, code, key, data, reply_to, priority, ttl, to_queue)
        self.connection.add_callback_threadsafe(cb)

    # Publish messages
    def _send(self, sender, code, key, data, reply_to='', priority=0, ttl=None, to_queue=False):
        self.publishing = self.connect_channel(self.publishing, 'publishing')
        # Detect format message
        fmt, msg = ('text', data) if isinstance(data, str) else ('json', json.dumps(data, default=json_encoder))

        headers = {'type': 'vlbi', 'sender': sender, 'code': code, 'format': fmt, 'utc': datetime.utcnow().isoformat()}
        properties = {'delivery_mode': 2, 'priority': priority, 'reply_to': reply_to, 'headers': headers,
                      'expiration': str(ttl) if ttl else None}

        try:
            exchange = '' if to_queue else self.exchange
            self.publishing.basic_publish(exchange, key, msg, pika.BasicProperties(**properties))
        except pika.exceptions.ChannelWrongStateError as err:
            raise RMQclientException(f'Publisher channel error{str(err)}')

    # Test that queue is alive
    def alive(self):
        # Ping same queue and read message
        self.ping(self.queue, to_queue=True)

        # Check is message is coming back (wait maximum time == self.ttl)
        self.consuming = self.connect_channel(self.consuming, 'consumer')
        start = datetime.now()
        try:
            while (datetime.now() - start).total_seconds() * 1000 < self.ttl:
                method, props, body = self.consuming.basic_get(self.queue)
                if method:
                    now = datetime.utcnow()
                    if props.headers.get('code', '') == 'ping':
                        dt = now - datetime.fromisoformat(props.headers['utc'])
                        self.consuming.basic_ack(method.delivery_tag)  # ACK message
                        return dt.total_seconds()
                    else: # Not the right message
                        self.consuming.basic_reject(method.delivery_tag)
        except (pika.exceptions.ConnectionClosedByBroker, pika.exceptions.ConnectionClosed,
                pika.exceptions.AMQPError, Exception) as err:
            raise RMQclientException(f'Test alive failed{str(err)}')
        raise RMQclientException(f'No answer after {int(self.ttl/1000)} seconds')

    # Send a ping to specific target
    def ping(self, target, to_queue=False, need_reply=False):
        return self.send(self.queue, 'ping', target, 'request status', priority=5, ttl=self.ttl,
                         to_queue=to_queue, reply_to=self.queue if need_reply else '')

    # Reply to ping
    def pong(self, sender, target, status):
        return self.send(sender, 'pong', target, {'status': status}, priority=5, ttl=self.ttl, to_queue=True)

    # Generic function doing nothing with message
    def do_nothing(self, properties, body):
        self.accept_last_msg()

    # Connect to queue and wait for message
    def monit(self, process_fnc, timeout_fnc=None, timeout=300):
        self.process_msg, self.process_timeout, self.timeout = process_fnc, timeout_fnc, timeout
        self.consuming = self.connect_channel(self.consuming, 'consumer')

        try:
            if self.process_timeout:
                self.timeout_id = self.connection.call_later(self.timeout, self.on_timeout)
            self.consuming.basic_qos(prefetch_count=1)
            self.consuming.basic_consume(queue=self.queue, on_message_callback=self.new_msg, auto_ack=False)
            self.consuming.start_consuming()
        except (pika.exceptions.ConnectionClosedByBroker, pika.exceptions.ConnectionClosed,
                pika.exceptions.AMQPError, Exception) as err:
            if self.close_requested:
                return
            self.add_error(str(err))
            raise RMQclientException(f'Monit connection lost {str(err)}')

    def new_msg(self, ch, method, properties, body):
        self._last_msg = (ch, method)
        if properties.headers.get('type', 'unknown') == 'vlbi':  # Valid VLBI message
            if self.process_timeout:
                self.connection.remove_timeout(self.timeout_id)
                self.timeout_id = self.connection.call_later(self.timeout, self.on_timeout)
            self.process_msg(properties.headers, body)
        else:
            self.acknowledge_msg()

    def on_timeout(self):
        try:
            self.timeout_id = self.connection.call_later(self.timeout, self.on_timeout)
            self.process_timeout()
        except Exception as e:
            self.warning(f'ON TIMEOUT {str(e)}')

    # Internal function to ack message (thread safe)
    def _ack_msg(self, ch, method):
        try:
            ch.basic_ack(method.delivery_tag)
        except Exception as ex:
            self.add_error('Could not ACK last message', str(ex))

    # Accept last
    def acknowledge_msg(self):
        ch, method = self._last_msg
        cb = functools.partial(self._ack_msg, ch, method)
        self.connection.add_callback_threadsafe(cb)

