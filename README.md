# sds011-mqtt

Forwards Enocean messages from a USB gateway to a MQTT broker. Not implemented is the direction back to the Enocean
USB gateway (due to missing devices).

It's implemented as python script and supposed to run as systemd service (handling restart, logging)


### Tested and supported Enocean devices

- windows/door handle Eltako FFG7B-rw (nearly identical to Eltako TF-FGB)


### Enocean USB gateway

The script is based on [Enocean(-Lib)](enocean-lib). Check out if there are some limitations. Hopefully all available
devices will do. (Tested with a DOSMUNG Gateway USB Stick with SMA Port, chipset TCM 310.)


### Additional features

- configurable MQTT last will / testament
  (e.g. an "OFFLINE" status can be predefined at MQTT level for connection interrupts)
- check sensor state based on repeated messages and send an configurable OFFLINE message if the device is silent
  for a configurable timeout.
- supports different message handler (see for samples in [sds011-mqtt.yaml.sample](./sds011-mqtt.yaml.sample)):
    - logging: just write Enocean message to logfile or console
    - generic: just sends what could be extracted
    - "Eltako FFG7B-rw"-specific JSON: tranform states to: OPEN, CLOSED, TILTED, OFFLINE, ERROR and last change time
- Live cycle management (restarts) are supposed to be handled by systemd.


## Startup

### Get access to USB stick
```bash
# enable access to Enocean USB stick (alternative set user mode directly)
sudo usermod -a -G dialout $USER
# logout & login
```

### Test working MQTT broker (here Mosquitto)
```bash
sudo apt-get install mosquitto-clients

# preprare credentials
SERVER="<your server>"
MQTT_USER="<user>"
MQTT_PWD="<pwd>"

# start listener
mosquitto_sub -h $SERVER -p 8883 -u $MQTT_USER -P $MQTT_PWD --cafile /etc/mosquitto/certs/ca.crt -i "client_sub" -d -t smarthome/#
# or
mosquitto_sub -h $SERVER -p 1883 -i "client_sub" -d -t smarthome/#

# send single message
mosquitto_pub -h $SERVER -p 8883 -u $MQTT_USER -P $MQTT_PWD --cafile /etc/mosquitto/certs/ca.crt -i "client_pub" -d -t smarthome/test -m "test_$(date)" -q 2
# or
mosquitto_pub -h $SERVER -p 1883 -i "client_pub" -d -t smarthome/test -m "test_$(date)" -q 2

# just as info: clear retained messages
mosquitto_pub -h $SERVER -p 1883 -i "client_pub" -d -t smarthome/test -n -r -d
```

### Prepare python environment
```bash
cd /opt
sudo mkdir sds011-mqtt
sudo chown pi:pi sds011-mqtt  # type in your user
git clone https://github.com/rosenloecher-it/sds011-mqtt sds011-mqtt

cd sds011-mqtt
virtualenv -p /usr/bin/python3 venv

# activate venv
source ./venv/bin/activate

# check python version >= 3.7
python --version

# install required packages
pip install -r requirements.txt
```

### Configuration

```bash
# cd ... goto project dir

cp ./sds011-mqtt.yaml.sample ./sds011-mqtt.yaml
```

Edit your `sds011-mqtt.yaml`. See comments too.

Choose one of the available devices (modules pathes), which will handle Enocean message differently:
- `src.device.log_device.LogDevice`: Log/print messages as it is.
- `src.device.generic_device.GenericDevice`: Forward messages as it is.
- `src.device.eltako_ffg7b_device.EltakoFFG7BDevice`
    - specific to "Eltako FFG7B-rw" devices; creates JSON
    - tranform states to (STATUS): OPEN, CLOSED, TILTED, OFFLINE, ERROR
    - "SINCE" contains th last change time
    - example
        ```
        {
            "STATUS": "CLOSED",
            "RSSI": -61,
            "TIMESTAMP": "2020-03-16T21:09:37.205911+01:00",
            "SINCE": "2020-03-15T19:09:37.205911+01:00"
        }
        ```

### Run

```bash
# see command line options
./sds011-mqtt.sh --help

# prepare your own config file based on ./sds011-mqtt.yaml.sample
./sds011-mqtt.sh -p -c ./sds011-mqtt.yaml
```

## Register as systemd service
```bash
# prepare your own service script based on sds011-mqtt.service.sample
cp ./sds011-mqtt.service.sample ./sds011-mqtt.service

# edit/adapt pathes and user in sds011-mqtt.service
vi ./sds011-mqtt.service

# install service
sudo cp ./sds011-mqtt.service /etc/systemd/system/
# alternativ: sudo cp ./sds011-mqtt.service.sample /etc/systemd/system//sds011-mqtt.service
# after changes
sudo systemctl daemon-reload

# start service
sudo systemctl start sds011-mqtt

# check logs
journalctl -u sds011-mqtt

# enable autostart at boot time
sudo systemctl enable sds011-mqtt.service
```

## Troubleshouting

There happend some very quick connects/disconnects from/to MQTT broker (Mosquitto) on a Raspberry Pi. The connection
was secured only by certificate. The problem went away after configuring user name and password for the MQTT broker.
On a Ubunutu system all was working fine even without user and password.

`sudo service sds011-mqtt status`

Mar 18 06:22:18 roofpi systemd[1]: sds011-mqtt.service: Current command vanished from the unit file, execution of the command list won't be resumed.

```
sudo systemctl disable sds011-mqtt.service
sudo rm /etc/systemd/system/sds011-mqtt.service
sudo systemctl daemon-reload

sudo cp ./sds011-mqtt.service /etc/systemd/system/
sudo rm /etc/systemd/system/sds011-mqtt.service
sudo service sds011-mqtt start
sudo systemctl enable sds011-mqtt.service
```


## Related projects

- Based on: [py-sds011](https://github.com/ikalchev/py-sds011)


## Maintainer & License

GPLv3 © [Raul Rosenlöcher](https://github.com/rosenloecher-it)

The code is available at [GitHub][home].

[home]: https://github.com/rosenloecher-it/sds011-mqtt

