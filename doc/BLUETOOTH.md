# Fine dust sensor SDS011 via Bluetooth

The sensor works best if connected to USB. You can buy "active" USB cables up to 10 meter length. I have never tried, but you will find a lot of negative reviews. Even 10 meter are not much if you have to go up and down a roof.

But putting the whole Raspberry Pi outside would be a severe security issue, because it's to easy to extract stored Wifi passwords. So I connected it via Bluetooth.

## Wiring

![bluetooth-wired](/home/hub/projects/sds011-mqtt/doc/bluetooth-wired.jpg)

The USB connector was replaced by a 230V AC to 5V DC power supply (e.g. [Amazon Germany](https://www.amazon.de/gp/product/B079138QY1/)). As Bluetooth module use a HC-05 or HC-06.

Make sure you cross the RX and TX wires between Bluetooth module and sensor. It took me some time to figure that out!

The sensor has a JST-XH plug socket (2.54 mm), but I was not able to crimp it properly. So I crimped all as Dupont connectors (also pin pitch of 2.54 mm).


## Configure Bluetooth on Raspberry Pi

It's recommended to use an external Bluetooth adapter for better transmission. Then an USB extension cable can be used to bring to the Bluetooth dongle as near as possible to the target. The Bluetooth target may be behind an outer wall, don't underestimate the signal loss.

Run: `hciconfig`

The one with bus "USB" is your choice, bus "UART" is the on-board device.

Disable the on-board Bluetooth dongle:
```bash
sudo hciconfig hci1 up
sudo hciconfig hci0 down
```
After reboot the Bluetooth adapter index could be changed!

"BD Address" is the Bluetooth ID within `bluetoothctl`.


### Paring

`sudo bluetoothctl`

Within "bluetoothctl" command mode:

```
# list Bluetooth adapters
list

# select the right adapter; format "00:11:22:33:FF:AD"
select <adapter_id>
select 00:11:22:33:FF:AD

power on
agent on
default-agent
pairable on
discoverable on

# unpairing devices connected to internal Bluetooth adapter didn't work for me
# remove 00:11:22:33:FF:EE
#   Failed to remove device: org.bluez.Error.NotReady
# just pair with the new adapter!

scan on
# your device will be listed
scan off

pair <device_id>
pair 00:11:22:33:FF:EE
# type in your pin (1234 for HC-06)
trust <device_id>
trust 00:11:22:33:FF:EE

info <device_id>
info 00:11:22:33:FF:EE

pairable off
paired-devices

```

### Check signal strength (RSSI)

```bash
# implicit adapter index == 0
sudo btmgmt find

# define adapter index (e.g. == 1 for an external adapter)
sudo btmgmt --index 1 find
```

Make sure the value is higher than **-60**.



### Prepare a serial port

```bash
sudo rfcomm bind 1 00:14:03:05:59:DF 1
sudo rfcomm bind 00:1A:7D:DA:71:0B 00:14:03:05:59:DF 1

sudo rfcomm release 1 00:14:03:05:59:DF
```

Binding the Bluetooth device to a serial port is best done by `ExecStartPre` within the service script.
