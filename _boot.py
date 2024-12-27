# This file is executed on every boot (including wake-boot from deepsleep)
# import esp
# esp.osdebug(None)
# import webrepl
# webrepl.start()

from main_system import main_system
system = main_system(safety_switch=True)
system.start_threads()