#!/usr/bin/env python3

import requests
import threading
import time

from enum import Enum
from datetime import datetime

class RelayState(Enum):
    ON = True
    OFF = False

class Shelly1():
    def __init__(self, host=None, http_timeout=1):
        '''shellyone module - https://www.shelly.cloud/en-us/products/product-overview/shelly-1-ul

        host - the hostname or IP address of the module - if not set, will default to 192.168.33.1
        http_timeout - amount of time in seconds an http request will wait to get a response
        '''
        if host:
            self.host = host
        else:
            self.host = "192.168.33.1"

        self.http_timeout = http_timeout

        self.shelly_base_url = f"http://{self.host}"

        # Initialize oscillation thread stop flag
        self._stop_oscillation = True

        # Initialize an oscillation counter
        self._oscillations = 0

    def status(self):
        '''get the status of the shelly

        returns: module status as JSON
        '''
        return requests.get(self.shelly_base_url + "/status", timeout=self.http_timeout).json()

    def get_relays(self):
        '''get a list of relays supported by the module

        returns: list of tuples - (id, shelly.RelayState)
        '''
        s = self.status()['relays']
        relays = []
        for i in range(len(s)):
            relays.append((i, RelayState.ON if s[i]['ison'] else RelayState.OFF))
        return relays

    def get_relay_state(self, relay_id):
        '''get the status of a relay by id

        relay_id: integer id of the relay

        returns: shelly.RelayState
        '''
        assert type(relay_id) == int

        return RelayState.ON if self.status()['relays'][relay_id]['ison'] else RelayState.OFF

    def power(self, relay_id, state):
        '''set the power state of the relay

        relay_id: relay to set power state
        state (bool): True == on; False == off

        returns: shelly.RelayState
        '''
        assert type(relay_id) == int
        assert type(state) == bool

        url_state = "off"
        if state:
            url_state = "on"

        if requests.get(self.shelly_base_url + f"/relay/{relay_id}?turn={url_state}", timeout=self.http_timeout).json()['ison']:
            return RelayState.ON
        else:
            return RelayState.OFF


    def toggle(self, relay_id):
        '''toggle the state of the relay

        relay_id: relay to toggle

        returns: shelly.RelayState
        '''
        assert type(relay_id) == int

        if self.get_relay_state(relay_id) == RelayState.ON:
            return self.power(relay_id, False)
        else:
            return self.power(relay_id, True)

    def oscillate(self, relay_id, period, block=True):
        '''oscillate between on and off

        relay_id: id of the relay to oscillate
        period: length of time in seconds in each power state, on and off, during oscillation
        block: whether or not this function will block

        returns: nothing if block==True, otherwise a handle to threading.Thread
        '''
        assert type(relay_id) == int
        assert type(period) in (int, float)
        assert period >= 0.05
        assert type(block) == bool

        if block:
            # Reset initial state of the flag
            self._stop_oscillation = False

            self._oscillations = 0
            while not self._stop_oscillation:
                self.toggle(relay_id)

                # TODO: thread safety?
                self._oscillations = self._oscillations + 1

                time.sleep(period)
        else:
            # "background" as a thread
            t = threading.Thread(target=self.oscillate, args=(relay_id, period,), daemon=True)
            t.start()
            return t

    def oscillate_timeout(self, relay_id, period, timeout, block=True, start_state=True, final_state=False):
        '''oscillate until timeout has elapsed

        relay_id: id of the relay to oscillate
        period: length of time in seconds in each power state, on and off, during oscillation
        timeout: amount of time in seconds after which oscillation halts
        block: whether or not this function will block
        final_state: state of the relay when oscillation halts (type RelayState)

        returns: nothing if block==True, otherwise a handle to threading.Thread
        '''
        assert type(relay_id) == int
        assert type(period) in (int, float)
        assert period >= 0.05
        assert type(timeout) == int
        assert timeout > 0
        assert type(block) == bool
        assert type(final_state) == bool

        def _stop_oscillation_in(period, timeout, final_state):

            # Reset initial state of the flag
            self._stop_oscillation = False

            current_epoch = datetime.now().timestamp()
            while datetime.now().timestamp() < (current_epoch + timeout):
                time.sleep(0.1)

            self._stop_oscillation = True

            # Sleep for 1x period duration to ensure that the oscillation thread has had time to
            # finish setting its final state and exit. Without this sleep, it is possible that we
            # encounter a race condition whereby the read (get_relay_state) happens before the last
            # alteration of the state by the oscillation thread...which is a dirty read, not good.
            time.sleep(period)

            if self.get_relay_state(relay_id).value != final_state:
                self.power(relay_id, final_state)

        # Set starting state
        if self.get_relay_state(relay_id).value != start_state:
            self.power(relay_id, start_state)
            time.sleep(period)

        self.oscillate(relay_id, period, block=False)

        # Background the stop thread
        t = threading.Thread(target=_stop_oscillation_in, args=(period, timeout,), \
            kwargs={"start_state": start_state, "final_state": final_state}, daemon=True)
        t.start()

        if block:
            t.join()

    def oscillate_cycles(self, relay_id, period, cycles, block=True, start_state=True, final_state=False):
        '''oscillate a specific cycle count

        relay_id: id of the relay to oscillate
        period: length of time in seconds in each power state, on and off, during oscillation
        cycles: number of cycles (a cycle is peak to peak)
        block: whether or not this function will block
        start_state: initial state of relay
        final_state: state of the relay when oscillation halts (type RelayState)

        returns: nothing if block==True, otherwise a handle to threading.Thread

        NOTE: Count is NOT incremented by change of state TO the start_state. Counting begins only
        after the initial start state is realized.
        '''
        assert type(relay_id) == int
        assert type(period) in (int, float)
        assert period >= 0.05
        assert type(cycles) == int
        assert cycles > 0
        assert type(block) == bool
        assert type(start_state) == bool
        assert type(final_state) == bool

        if block:
            # Reset initial state of the flag
            self._stop_oscillation = False

            # Set starting state
            if self.get_relay_state(relay_id).value != start_state:
                self.power(relay_id, start_state)
                time.sleep(period)

            # Reset the initial count of oscillations
            self._oscillations = 0

            while not self._stop_oscillation and self._oscillations < cycles:
                self.toggle(relay_id)

                time.sleep(period)

                # TODO: thread safety?
                # One toggle is half a cycle
                self._oscillations = self._oscillations + 0.5

            if self.get_relay_state(relay_id).value != final_state:
                self.power(relay_id, final_state)
        else:
            # "background" as a thread
            t = threading.Thread(target=self.oscillate_cycles, args=(relay_id, period, cycles,), \
                kwargs={"start_state": start_state, "final_state": final_state}, daemon=True)
            t.start()
            return t

    def stop_oscillation(self):
        '''stop an oscillation operation'''
        self._stop_oscillation = True
