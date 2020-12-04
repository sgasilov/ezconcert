"""Common functions, objects and data"""

from epics import PV
import time


class PVObject(object):
    def __init__(self):
        self.pending = []
        self.connected = 0
        self.retries = 5
        self.sleep = 0.05

    def add_pv(self, pv_name, conn_callback=True, callback=False, *args, **kwargs):
        """
        Add PV to device.

        Args:
            pv_name (str): Full PV name
            conn_callback (bool): use self.on_conn_change when connection changes (default = True)
            callback (bool): use self.on_value_change when value changes (default = False)

        Returns:
            dev (PV): A :class:`epics.PV` object.
        """
        print(pv_name)
        if conn_callback:
            conn_callback = self.on_conn_change
        else:
            conn_callback = None
        if callback:
            callback = self.on_value_change
        else:
            callback = None
        for trial in range(self.retries):
            try:
                dev = PV(
                    pv_name,
                    connection_callback=conn_callback,
                    callback=callback,
                    *args,
                    **kwargs
                )
                i = dev.info
                if i is None:
                    print("...not valid")
                self.pending.append(dev)
                c = dev.connect()
                # print(c)
                if c:
                    self.connected += 1
                    break
            except TypeError:
                print(
                    "...Error occured connecting to PV. Try {} of {}.".format(
                        trial + 1, self.retries
                    )
                )
                time.sleep(self.sleep)
        return dev

    @staticmethod
    def on_conn_change(pvname=None, conn=None, **kwargs):
        """
        Call-back for connection status changes.

        Args:
            pvname (str): pv name
            conn (bool): connection status
            kwargs : other input arguments

        Returns:
            None
        """
        print("PV connection has changed: {} = {}".format(pvname, repr(conn)))

    @staticmethod
    def on_value_change(pvname=None, value=None, host=None, **kwargs):
        """
        Call-back for value change

        Args:
            pvname (str): pv name
            value (type of value): the latest value from the PV
            host (str): address:port of host
            kwargs: other input arguments

        Returns:
            None
        """
        print("Value changed: {} ({}) = {}".format(pvname, host, repr(value)))

    def add_callback(self, pv_obj, callback):
        """
        Add a Call-back for value change
        
        Args:
            pv_obj (PV): PV object to add call-back to
            callback (function): call-back function to connect
            
        Returns:
            pv_obj (PV): PV object
        """
        pv_obj.add_callback(callback)
        return pv_obj
    