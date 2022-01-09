# PiPagingConsole
Two-way radio paging encoder for the Raspberry Pi.  Designed to be used with a touchscreen display.  Currently supports two-tone sequential, 5-tone, and DTMF paging formats. 

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

## Operation

## Tone Configuration JSON file
A sample JSON configuration file showing examples of two-tone sequential, five-tone sequential (CCIR), and DTMF tones is below.  

#### "tone" objects
tone objects are used for two-tone and five-tone paging formats and consist of a "freq" and "duration" field for each tone segment.  

### "dtmf" objects
dtmf objects are used for DTMF paging formats (including Knox) and consist of a "f1", "f2" and "duration" field for each tone segment.  

If a gap is needed between tone segements, simply add an additional segment with frequency (or f1 and f2) set to 0 and duration as desired.  

```
{"Tones": 
 [
  {"description": "Two Tone Example", "tone": [{"freq": 1372.9, "duration": 1}, {"freq": 1573.5, "duration": 3}]},
  {"description": "Five Tone Example", "tone": [{"freq": 1124, "duration": 0.1}, {"freq": 1197, "duration": 0.1}, {"freq": 1275, "duration": 0.1}, {"freq": 1358, "duration": 0.1}, {"freq": 1446, "duration": 0.1}]},
  {"description": "DTMF Example", "dtmf": [{"f1": 1321.2,"f2":600, "duration": 0.5}, {"f1": 1513.5,"f2":700, "duration": 0.5},{"f1": 1321.2,"f2":600, "duration": 0.5}]}
 ]
}
```

## Settings JSON file
