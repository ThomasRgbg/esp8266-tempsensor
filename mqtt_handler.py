# History:
# v5 - Baseline (= don't remember)
# v6 - Fixed prints
# v7 - Add support to filter zero values for pubisher
# v8 - Publish zero values after action due to a message 


import machine
import time

from ubinascii import hexlify
from umqtt.robust import MQTTClient
 
class MQTTHandler:
    def __init__(self, name, server):
        self.mqtt = MQTTClient(hexlify(machine.unique_id()), server, keepalive=0)
        self.name = name
        self.actions = {}
        self.publishers = {}  # [varialbe, publish zero values]
        self.connect()
        self.mqtt.set_callback(self.handle_mqtt_msgs)
        self.publish_all_after_msg = True
        self.version = 7

    def connect(self):
        print('mqtt_handler.connect() Check if MQTT is already connected')
        if self.isconnected():
            self.mqtt.disconnect()
        try:
            print('mqtt_handler.connect() Not connected, so lets connect')
            self.mqtt.connect()
        except OSError:
            print("mqtt_handler.connect() MQTT could not connect")
            return False
                
        time.sleep(3)
        if self.isconnected():
            self.resubscribe_all()
            return True
        else:
            # Some delay to avoid system getting blocked in a endless loop in case of 
            # connection problems, unstable wifi etc.
            time.sleep(5)
            return False
        
    def isconnected(self):
        try:
            self.mqtt.ping()
            self.mqtt.check_msg()
        except OSError:
            print("mqtt_handler.isconnected() MQTT not connected - Ping not successfull")
            return False
        except AttributeError:
            print("mqtt_handler.isconnected() MQTT not connected - Ping not available")
            return False
        
        return True

    def publish_generic(self, name, value):
        topic = self.name + b'/' + bytes(name, 'ascii')
        print("mqtt_handler.publish_generic() Publish: {0} = {1}".format(topic, value))
        self.mqtt.publish(topic, str(value))

    def handle_mqtt_msgs(self, topic, msg):
        print("mqtt_handler.handle_mqtt_msgs() Received MQTT message: {0}:{1}".format(topic,msg))
        if topic in self.actions:
            print("mqtt_handler.handle_mqtt_msgs() Found registered function {0}".format(self.actions[topic]))
            self.actions[topic](msg)
            if self.publish_all_after_msg:
                self.publish_all(force=True)

    def register_action(self, topicname, cbfunction):
        topic = self.name + b'/' + bytes(topicname, 'ascii')
        print("mqtt_handler.register_action() Get topic {0} for {1}".format(topic, cbfunction))
        if self.isconnected():
            print('mqtt_handler.register_action() MQTT connected, try to register')
            self.mqtt.subscribe(topic)
        self.actions[topic] = cbfunction
        
    def register_publisher(self, topicname, function, zeros=True):
        topic = self.name + b'/' + bytes(topicname, 'ascii')
        print("mqtt_handler.register_publisher() Get topic {0} for {1}, zeros {2}".format(topic, function, zeros))
        self.publishers[topic] = [function, zeros]
        
    def publish_all(self, force=False):
        for topic in self.publishers:
            function, zeros = self.publishers[topic]
            value = function()
            if value is not None:
                if zeros or force:
                    print("mqtt_handler.publish_all() Publish: {0} = {1}".format(topic, value))
                    self.mqtt.publish(topic, str(value))
                elif value == 0 or value == 0.0:
                    print("mqtt_handler.publish_all() Discard: {0} = {1}".format(topic, value))
                else:
                    print("mqtt_handler.publish_all() Publish: {0} = {1}".format(topic, value))
                    self.mqtt.publish(topic, str(value))
        
    def resubscribe_all(self):
        for topic in self.actions:
            self.mqtt.subscribe(topic)
