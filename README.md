# PiPagingConsole
Two-way radio paging encoder for the Raspberry Pi.  Designed to be used with a touchscreen display.  Currently supports two-tone sequential, 5-tone, and DTMF paging formats.  Audio and PTT (and optional COR) via the radio's accessory connector. Select the tones, click send, and then use the radio's hand mic for voice dispatch after the tones have been sent.  

![Screenshot](https://github.com/aaknitt/PiPagingConsole/blob/main/images/MainScreen.PNG)

## Features
- Uses the Raspberry Pi's onboard sound card to send audio to the radio.
- Select multiple tones to send as a "stacked page"
- GPIO pins used to control radio transmit (external transistor circuit required)
- Optional Busy Channel Lockout using radio COR output
- Optional sidetone audio output using a second audio output device
- Optional sidetone alert after tones are done sending
- Optional automatic clearing of tone selections during send, after send, or after a timeout
- Optional PIN number protection for settings
- JSON file to configure tones
- Will run on Windows for testing (but without GPIO for PTT and COR)

Works well with Raspberry Pi Touchscreen enclosures such as this one:  https://www.amazon.com/gp/product/B08T5LCTKT

## Radio Interface
The script uses GPIO pins on the Raspberry Pi to interface with the two-way radio PTT input and (optionally) COR output.  Pin 11 of the I/O connector (GPIO17) is used as the PTT output and pin 15 of the I/O connector (GPIO22) is used as the COR input.  The PTT output is active high from the Raspberry Pi and is intended to drive a 2N3904 (or similar) transistor in open collector configuration to interface with a radio that expects the PTT line to be active low (ground the pin to activate PTT).

![PTT Circuit](https://github.com/aaknitt/PiPagingConsole/blob/main/images/PTTcircuit.PNG)

The COR input is pulled up internally in the Raspberry Pi and is considered active when pulled low.  If the radio has an active high COR output an additional interface circuit may be required to change polarity.

Future versions of the software may allow for GPIO configuration/selection in the config.json file.  An add-on shield for the Raspberry Pi with multiple PTT and COR circuits (to support multiple radios and/or channel steering with a single paging console) is in development.  

## Tone Configuration JSON file
A sample JSON configuration file showing examples of two-tone sequential, five-tone sequential (CCIR), and DTMF tones is below.  

```
{"Tones": 
 [
  {"description": "Two Tone Example", "tone": [{"freq": 1372.9, "duration": 1}, {"freq": 1573.5, "duration": 3}]},
  {"description": "Five Tone Example", "tone": [{"freq": 1124, "duration": 0.1}, {"freq": 1197, "duration": 0.1}, {"freq": 1275, "duration": 0.1}, {"freq": 1358, "duration": 0.1}, {"freq": 1446, "duration": 0.1}]},
  {"description": "DTMF Example", "dtmf": [{"f1": 1321.2,"f2":600, "duration": 0.5}, {"f1": 1513.5,"f2":700, "duration": 0.5},{"f1": 1321.2,"f2":600, "duration": 0.5}]}
 ]
}
```

#### "tone" objects
tone objects are used for two-tone and five-tone paging formats and consist of a "freq" and "duration" field for each tone segment.  

#### "dtmf" objects
dtmf objects are used for DTMF paging formats (including Knox) and consist of a "f1", "f2" and "duration" field for each tone segment.  

If a gap is needed between tone segements, simply add an additional segment with frequency (or f1 and f2) set to 0 and duration as desired.  


## Settings Menu & PIN
![Settings](https://github.com/aaknitt/PiPagingConsole/blob/main/images/Settings.PNG) ![PINentry](https://github.com/aaknitt/PiPagingConsole/blob/main/images/PINentry.PNG)
Settings are stored in the config.json file.  The settings may be changed by clicking the "Settings" button on the main screen.  The settings menu may be optionally protected by a PIN number specified in the config.json file (note that the PIN is specified in the JSON as a numeric string):
```
"Settings PIN":"12345"
```

