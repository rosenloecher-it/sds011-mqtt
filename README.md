# SDS011-MQTT

... is a Linux Python script/service to control the fine dust sensor SDS011 via MQTT. 


## Motivation 

The goal was to put the sensor outside under the roof and control it from inside with a Raspberry Pi. Therefor the USB connection was replaced with Bluetooth (through the wall).

The measurements are published to a MQTT server, from where it can be processed further. 

The measurements should reflect when my neighbor fires his wood stove especially private waste combustion, so that I can switch off my air-handling system of my house before the smell (not the fume) is spread all over.

  ![Screenshot Grafana](./doc/fume-grafana.png)

Some further information about my motivation can be found [here](./doc/MOTIVATION.md).


## Features

The sensor was easily to control as long it was inside a room and connected via USB. As soon the sensor was mounted under the roof, problems occurred. The main problem seems to be humidity. 

The sensor is specified up to 70% humidity, which you reach in middle Europa in every normal night. Above th limits the sensor would stop without any clear information. There are no error codes, you get just nothing. Even if the humidity got within the limits, the sensor wouldn't start delivering measurements. I had to switch off/on the power manually. In the end, I put much more effort into this project and added more features than I had anticipated. So it's not so lean any more as intended.

It does:
- Controls a SDS011 fine dust sensor
- Trigger measurement in configurable intervals (Option for adaptive measurement intervals to detect dust peaks)
- Deliver measurements as JSON to MQTT
- Send sensor to sleep after measurements
- Option to switch on/off the sensor by an external power relay via MQTT command (separate control channel)
- Automatic deactivation of sensor  
    - If humidity/temperature exceeds configured limits (provide humidity/temperature via MQTT).
    - for specific time ranges (configuration)
    - via MQTT command channel (set to "HOLD" by smart home system)
- Operation system: Linux incl. Raspbian for Raspberry Pi
- systemd service script provided
- Programmed with Python 3.6


## Startup

### prepare connection

In case you connect the sensor via USB you may need to set some permissions:  
```bash
# enable access to Enocean USB stick (alternative set user mode directly)
sudo usermod -a -G dialout $USER
# logout & login
```

I connect it via Bluetooth. See my notes [here](./doc/BLUETOOTH.md).


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


### Run

```bash
# prepare your own config file based on ./sds011-mqtt.yaml.sample . See comments!
cp ./sds011-mqtt.yaml.sample ./sds011-mqtt.yaml

# see command line options
./sds011-mqtt.sh --help

# run
./sds011-mqtt.sh -p -c ./sds011-mqtt.yaml
```

## Register as systemd service
```bash
# prepare your own service script based on sds011-mqtt.service.sample
cp ./sds011-mqtt.service.sample ./sds011-mqtt.service

# edit/adapt pathes and user in sds011-mqtt.service
vi ./sds011-mqtt.service
# configure optional `ExecStartPre` commands. e.g. prepareing a serial Bluetooth port

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


## Troubleshooting

There happened some very quick connects/disconnects from/to MQTT broker (Mosquitto) on a Raspberry Pi. The connection was secured only by certificate. The problem went away after configuring user name and password for the MQTT broker. On a Ubuntu system all was working fine even without user and password.

`sudo service sds011-mqtt status`

Mar 18 06:22:18 server systemd[1]: sds011-mqtt.service: Current command vanished from the unit file, execution of the command list won't be resumed.

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

MIT © [Raul Rosenlöcher](https://github.com/rosenloecher-it)

The code is available at [GitHub][home].

[home]: https://github.com/rosenloecher-it/sds011-mqtt

