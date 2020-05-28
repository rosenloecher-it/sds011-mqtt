# Motivation for SDS011-MQTT

SDS011 is a sensor to measure fine dust concentration in air. The last years there were lost of discussions in public about fine dust pollution which lead in the end to a ban on Diesel-powered vehicles in Germany. That's not my concern and I think there are more important things. OK, I drive a Diesel car by myself.

Normally the air at my home is quite good. There is no reason to worry about traffic. But I have neighbors who run a private waste combustion or at least heat with wood stoves. And regularly in winter it smells ugly outside. Unfortunately my own house has a ventilation system (with waste heat recovery)  which sucks in continuously the outside air and spread in several room (especially in living and sleeping room). So the outside smell comes in, quickly. (The smell gets in, not the visible fumes, but it's still annoying enough.)

I haven't tried to convince my neighbors to learn to stay in an unheated living room in winter. It feels like a final shot. I stumbled over the fine dust sensor and the question was: Can fine dust measurements indicate an heating wood stove? (The wind direction doesn't matter as long the fine dust sensor is located near the air intake.) Then I would be able to switch of my ventilation system, which then were an easy exercise.

In principle the idea works. The fine dust measurements correlate to the fume/smell.

The highest value (peak) I measured were 496 µg/m³ (PM 10) and 352 µg/m³ (PM 2.5). These are peak values and not comparable with dust average limits (40 µg/m³) for ban on Diesel-powered vehicles in Germany. Normally the dust values varies between 1 and 15 µg/m³.

![Screenshot Grafana](./fume-grafana.png)

Just to get an impression: So my neighbors house looked like when the peak value was measured.
The wind was blowing the fumes to my house. (It's a comparable to barbecue with wet coal.)

![fume-house](./fume-house.jpg)

In practice, the sensor is very peaky about humidity. The sensor is specified up to 70% humidity, which is topped every normal night in middle Europa and when it's raining.

When the sensor runs at humid circumstances, it will stop delivering values. Unfortunately there is no error code or other information, what's going wrong.

Even though you regard these limit (switch off the sensor by power switch at humid conditions), the sensor malfunction quite often. For example, sometimes after a rainy period/day it takes several hours under proper condition to recover and send values again. For hours I get exactly the same measurement values. Does the sensor get soaked?! But this malfunction occurs also under normal conditions, where no reason is so obvious.

For such ambiguous behavior I deigned a specific working mode: The sensor is powered on and the fan will run until a positive measurement and hopefully drying the sensor (theory). If there is no success after 10 (configurable) shots, the service will stop. Then the sensor get powered off and restarted by systemd after 5 minutes.







