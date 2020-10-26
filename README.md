# Pi-cooler
Pi-cooler is a Raspberry Pi's cooler fan controller software. It can be used to attach a cooler fan to a Raspberry Pi and control it so that it can be turned on when necessary and turned off when unnecessary. Also, this software can be used to attach a power button to reboot and power off your Rasberry Pi, supporting the appropriate indicator LEDs.

## Why do I need this?

You may need Pi-cooler, for instance, in these situations:
- Your Raspberry Pi's cooler fan is too loud to be on all the time, so you need it to run only when necessary.
- Your Raspberry Pi is on a limited power source, and need to minimize power usage.
- You want to attach a power/restart button to your Raspberry Pi.
- You want to attach a status indicator LED to your Raspberry Pi.

## Is my hardware compatible?

To control a 3-volt cooler fan, you can just plug it into any appropriate free pin on the GPIO.  
![Representation of the 3-volt cooler fan circuit](circuit-examples/3v-CoolerFan.png)  
  
To control a 5-volt cooler fan, you will also need a NPN or PNP transistor.  
![Representation of the 5-volt cooler fan circuit](circuit-examples/5v-CoolerFan.png)  
  
To attach a power button, you just need a button connected into any appropriate free pin on the GPIO, just as the LEDs do.  
![Representation of the button circuit](circuit-examples/Button.png)  
![Representation of the LED circuit](circuit-examples/LED.png)

## How to setup?

You can setup your working environment by using Pi-cooler's build-in setup. Just execute the program using a terminal and the setup sequence will be presented to you:  
`pip3 install -r requirements.txt && python3 pi-cooler.py config.json`  
You can replace the optional parameter _config.json_ with whatever path you want: this is where the settings will be saved.

## How to run?

After setup, you can run the program by executing the following command in a terminal (remember to replace _config.json_ with the path to the appropriate file):  
`python3 pi-cooler.py config.json`  

However, it's recommended that you add Pi-cooler to the boot sequence of your Raspberry Pi instead, so that you don't need to start the program manually everytime. During setup, the program will remind you to do so, but if you forget, the simplest way is by adding the following command to the _rc.local_ file (usually located at "/etc/rc.local"):  
`python3 PROG_PATH CONFIG_PATH`  

**Important:** Don't forget to replace PROG_PATH with the full path to the _pi-cooler.py_ file, and CONFIG_PATH with the full path to the _config.json_ file generated during setup. Also, the program will only be able to shutdown or restart the system if it's running as super user (_sudo_).

## How to contribute?

You have to follow some steps in order to contribute to the project:
1. Open a new Issue, describing your contribution.
2. Fork the repository.
3. Do whatever editions in the forked repository.
4. Open a new Pull Request, with reference to the opened Issue.
