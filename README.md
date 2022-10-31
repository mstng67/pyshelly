# pyshelly
Python API for Shelly products

## Usage
This usage guide assumes that you have connected to your Shelly 1's provided WiFi connection.

For some basic usage:
```py
from shelly import Shelly1

# Create an object that represents our Shelly 1 relay
s = Shelly1()

# JSON representation of the status of the relay
s.status()

# Switch the relay with ID == 0 on
s.power(0, True)

# Switch the relay with ID == 0 off
s.power(0, False)

# Toggle relay with ID == 0 (on the Shelly 1, there is only one relay, but there could be more in other products)
s.toggle(0)
```

NOTE: This project only supports the Shelly 1 since it is the only hardware from Shelly that I currently have.

## TODOs
- Integration with poetry
- Thread safety
- Username and password support
- Settings adjustment support
- Add support for more Shelly products