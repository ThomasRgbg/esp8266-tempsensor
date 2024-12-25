from machine import Pin, I2C, reset, RTC, unique_id, Timer, WDT, UART
import time

import uasyncio
import gc
import micropython

from math import log

import dht

from mqtt_handler import MQTTHandler

#####
# Schematic/Notes
######

# GPIO4 = DHT11

#####
# Housekeeping
#####

count = 1
errcount = 0

def get_count():
    global count
    return count

def get_errcount():
    global errcount
    return errcount

#####
# Watchdog
#####

class Watchdog:
    def __init__(self, interval):
        self.timer = Timer(-1)
        self.timer.init(period=(interval*1000), mode=Timer.PERIODIC, callback=self.wdtcheck)
        self.feeded = True

    def wdtcheck(self, timer):
        if self.feeded:
            print("Watchdog feeded, all fine")
            self.feeded = False
        else:
            print("Watchdog hungry, lets do a reset in 5 sec")
            time.sleep(5)
            reset()

    def feed(self):
        self.feeded = True
        print("Feed Watchdog")

wdt = Watchdog(interval = 120)
wdt.feed()


#####
# dht11
#####

dht = dht.DHT11(Pin(4))
# dht.measure()
# dht.temperature() # eg. 23 (°C)
# dht.humidity()    # eg. 41 (% RH)

#####
# MQTT setup
#####

# time to connect WLAN, if marginal reception
time.sleep(5)

sc = MQTTHandler(b'myhome/tempsensor1', '192.168.0.100')

#####
# Task definition
#####

async def housekeeping():
    global errcount
    global count
    await uasyncio.sleep_ms(1000)

    while True:
        print("housekeeping() - count {0}, errcount {1}".format(count,errcount))
        wdt.feed()
        gc.collect()
        micropython.mem_info()

        # Too many errors, e.g. could not connect to MQTT
        if errcount > 20:
            reset()

        count += 1
        await uasyncio.sleep_ms(60000)



async def handle_dht():
    while True:
        dht.measure()
        print("handle_dht() - Temperature {0} C, Humidity {1}%".format(dht.temperature(), dht.humidity()))

        A = 17.27
        B = 237.7
        alpha = ((A * dht.temperature()) / (B + dht.temperature())) + log(dht.humidity()/100.0)
        dew =  (B * alpha) / (A - alpha)
        print("handle_dht() - Dewpoint {0} C".format(dew))
        if sc.isconnected():
            sc.publish_generic('temperature', dht.temperature())
            sc.publish_generic('humidity', dht.humidity())
            sc.publish_generic('dewpoint', dew)
        await uasyncio.sleep_ms(60000)


async def handle_mqtt_tx():
    global errcount
    while True:
        if sc.isconnected():
            print("handle_mqtt_tx() - connected, do publish")
            sc.publish_all()
            await uasyncio.sleep_ms(58000)
        else:
            print("handle_mqtt_tx() - MQTT not connected - try to reconnect")
            sc.connect()
            errcount += 1
            await uasyncio.sleep_ms(18000)

        await uasyncio.sleep_ms(2000)

async def handle_mqtt_rx():
    global errcount
    while True:
        if sc.isconnected():
            # print("handle_mqtt_rx() - connected, wait for msg")
            sc.mqtt.wait_msg()

        # errcount += 1
        await uasyncio.sleep_ms(1000)



####
# Main
####

print("main_loop")

main_loop = uasyncio.get_event_loop()

main_loop.create_task(handle_mqtt_tx())
main_loop.create_task(handle_mqtt_rx())
main_loop.create_task(handle_dht())
main_loop.create_task(housekeeping())

main_loop.run_forever()
main_loop.close()

