import machine   # type: ignore

# Note: depends on I2C pins being same on all leafs!
_SDA = 1
_SCL = 2
_i2c = machine.I2C(1, scl=machine.Pin(_SCL), sda=machine.Pin(_SDA), freq=400000)

# compute board specific "signature" based on i2c addresses
_signature = " ".join([ f"0x{x:02x}" for x in _i2c.scan() ])

# no deinit on ESP32?
# __i2c.deinit()

# import appropriate definitions
if _signature   == "0x40 0x48 0x68":
    from .leaf01 import *
elif _signature == "0x55":
    pass
    # from .leaf02 import *
else:
    # this should not happen
    raise ImportError("no bsp")        

