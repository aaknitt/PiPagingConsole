#Copyright 2022 Andy Knitt
#
#TO DO
# - flush audio
# - Multiple radio PTT GPIO options - add to config.json
# - Channel steering GPIO options - add to config.json
# - Shutdown Pi in settings menu
# - Button colors in json file
# - Auto layout for more than 12 tone sets - adjust widths & fonts?
# - Audio files for BCL and "tones done sending" instead of beeps?

from tkinter import *
from tkinter import ttk
import json
import collections
import time
import _thread
from threading import Thread
import pyaudio
import numpy as np
import math
import subprocess

try:
	import RPi.GPIO as GPIO
	running_on_pi = True
except:
	running_on_pi = False

if running_on_pi == True:
	GPIO.setmode(GPIO.BOARD)
	PTT_PIN = 11 #GPIO17
	COR_PIN = 15 #GPIO22
	GPIO.setup(PTT_PIN, GPIO.OUT)
	GPIO.output(PTT_PIN, GPIO.LOW)
	GPIO.setup(COR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

f = open('config.json','r')
config = json.load(f, object_pairs_hook=collections.OrderedDict)
f.close()

f = open('tones.json','r')
tones = json.load(f,object_pairs_hook=collections.OrderedDict)
f.close()
last_select_time = time.time()
new_pin = ""

def update_bar(total_time):
	start_time = time.time()
	elapsed_time = 0
	while elapsed_time < total_time:
		time.sleep(.1)
		elapsed_time = time.time()-start_time
		barvar.set(int(elapsed_time/total_time*100))
		if clearButton['text'] == 'CLEAR':
			barvar.set(0)
			return
	
def wait_for_cor():
	cancel = 0
	last_COR_active_time = time.time()
	def set_cancel():
		nonlocal cancel
		cancel = 1
	def disable_event():
		pass
	statvar.set("Status: Waiting for channel to clear")
	statusLabel.configure(foreground="yellow")
	x = root.winfo_x()
	y = root.winfo_y()
	dx = int(root.winfo_width()/2)
	dy = int(root.winfo_height()/2)
	top = Toplevel()
	top.protocol("WM_DELETE_WINDOW", disable_event)
	w = 300
	h = 300
	#print("x: " + str(x) + "y: " + str(y) + "dx: " + str(dx) + "dy: " + str(dy))
	#print("%dx%d+%d+%d" % (w, h, x + dx, y + dy))
	#top.geometry("%dx%d+%d+%d" % (w, h, x + dx, y + dy))
	top.title('BUSY')
	Message(top, text='Channel is currently busy, waiting before sending').pack()
	forceSendButton = Button(top,text="FORCE SEND",command=top.destroy).pack(pady=10)
	cancelSendButton = Button(top,text="CANCEL SEND",command=set_cancel).pack(pady=10)
	top.geometry("200x300+800+416")
	play_beep(600,.1,4)
	while 1:
		if cancel == 1:
			statusLabel.configure(foreground="blue")
			statvar.set("Status: Idle")
			barvar.set(0)
			for i,button in enumerate(buttonlist):
				button.config(state=NORMAL)
			sendButton.config(state=NORMAL)
			top.destroy()
			time.sleep(.1)
			return 0
		if running_on_pi == True:
			if GPIO.input(COR_PIN)==0:
				#COR is still active
				last_COR_active_time=time.time()
		if time.time()-last_COR_active_time > config['Busy Channel Lockout Debounce']:
			top.destroy()
			time.sleep(.1)
			statusLabel.configure(foreground="blue")
			return 1
		try:
			top.state() #check to see if our toplevel still exists
		except:
			statusLabel.configure(foreground="blue")
			time.sleep(.1)
			return 1  #if not, it was destroyed by the user pressing FORCE SEND
			
def play_dtmf(f1,f2,duration,volume,output_device='radio'):
	points = int(BITRATE * duration)
	times = np.linspace(0, duration, points, endpoint=False)
	#https://stackoverflow.com/questions/1165026/what-algorithms-could-i-use-for-audio-volume-level
	scale_factor = (math.pow(10,volume)-1)/(10-1)
	output = np.array(np.sin(times*f1*2*np.pi)*32767.5*scale_factor*.5, dtype=np.int16) + np.array(np.sin(times*f2*2*np.pi)*32767.5*scale_factor*.5, dtype=np.int16)
	output = np.append(output,np.zeros(int(.01*BITRATE)))
	output = output.astype(np.int16)  #after appending the zeros we need to set the data type back to int16
	if output_device == 'radio':
		radiostream.write(output.tobytes())
	elif output_device == 'sidetone':
		sidetonestream.write(output.tobytes())
	
def play_tone(frequency,duration,volume,output_device='radio'):
	points = int(BITRATE * duration)
	times = np.linspace(0, duration, points, endpoint=False)
	#https://stackoverflow.com/questions/1165026/what-algorithms-could-i-use-for-audio-volume-level
	scale_factor = (math.pow(10,volume)-1)/(10-1)
	output = np.array(np.sin(times*frequency*2*np.pi)*32767.5*scale_factor, dtype=np.int16)
	output = np.append(output,np.zeros(int(.01*BITRATE)))  #append some zeros to make sure all audio gets flushed out
	output = output.astype(np.int16)  #after appending the zeros we need to set the data type back to int16
	if output_device == 'radio':
		radiostream.write(output.tobytes())
	elif output_device == 'sidetone':
		sidetonestream.write(output.tobytes())

def play_beep(frequency,duration,repetitions):
	for k in range(repetitions):
		play_tone(frequency,duration,sidetoneVolume.get()/100,'sidetone')
		time.sleep(duration)

def send_thread():
	#loop through once to get total duration of this stacked page for the status bar
	total_time = 0
	for i,button in enumerate(buttonlist):
		if intvarlist[i].get() == 1:
			if 'tone' in tones['Tones'][i]:
				tone = tones['Tones'][i]['tone']
			elif 'dtmf' in tones['Tones'][i]:
				tone = tones['Tones'][i]['dtmf']
			for tonesegment in tone:
				total_time = total_time + tonesegment['duration']
			total_time = total_time + .5
	global last_select_time
	last_select_time = time.time()+total_time
	if total_time > 0:
		#loop through again to disable buttons
		for i,button in enumerate(buttonlist):
			button.config(state=DISABLED)
		sendButton.config(state=DISABLED)
		cor_result = 1
		if running_on_pi == True:
			if config['Busy Channel Lockout']==1 and GPIO.input(COR_PIN) == 0:
				print("COR ACTIVE!!!!")
				cor_result = wait_for_cor()
		if cor_result == 0:
			#send was cancelled while waiting for COR
			return
		_thread.start_new_thread(update_bar,(total_time,))
		#loop through again to actually send
		clearButton.config(text="CANCEL")
		if running_on_pi == True:
			GPIO.output(PTT_PIN, GPIO.HIGH)
		time.sleep(.1)
		for i,button in enumerate(buttonlist):
			if intvarlist[i].get() == 1:
				statvar.set("Status: Sending " + tones['Tones'][i]['description'])
				if 'tone' in tones['Tones'][i]:
					tone = tones['Tones'][i]['tone']
				elif 'dtmf' in tones['Tones'][i]:
					tone = tones['Tones'][i]['dtmf']
				for tonesegment in tone:
					if 'tone' in tones['Tones'][i]:
						t1 = Thread(target=play_tone, args=(tonesegment['freq'],tonesegment['duration'],config['Radio Volume']/100,'radio'))
						if config['Sidetone']==1:
							t2 = Thread(target=play_tone, args=(tonesegment['freq'],tonesegment['duration'],sidetoneVolume.get()/100,'sidetone'))
						t1.start()
						if config['Sidetone']==1:
							t2.start()
						t1.join()
						if config['Sidetone']==1:
							t2.join()
					elif 'dtmf' in tones['Tones'][i]:
						play_dtmf(tonesegment['f1'],tonesegment['f2'],tonesegment['duration'],config['Radio Volume']/100,sidetoneVolume.get()/100)
						t1 = Thread(target=play_dtmf, args=(tonesegment['f1'],tonesegment['f2'],tonesegment['duration'],config['Radio Volume']/100,'radio'))
						if config['Sidetone']==1:
							t2 = Thread(target=play_dtmf, args=(tonesegment['f1'],tonesegment['f2'],tonesegment['duration'],sidetoneVolume.get()/100,'sidetone'))
						t1.start()
						if config['Sidetone']==1:
							t2.start()
						t1.join()
						if config['Sidetone']==1:
							t2.join()
				if config["Clear during send"] == 1:
					intvarlist[i].set(0)
				time.sleep(.5)
		#DEACTIVATE PTT HERE
		clearButton.config(text="CLEAR")
		if running_on_pi == True:
			GPIO.output(PTT_PIN, GPIO.LOW)
		statusLabel.configure(foreground="red")
		statvar.set("Status: SEND COMPLETE - READY FOR VOICE TRANSMISSION")
		if config["Alert tone"] == 1:
			duration = .1
			repetitions = 4
			play_beep(1000,duration,repetitions)
			time.sleep(5-duration*2*repetitions)
		else:			
			time.sleep(5)
		if config["Clear after send"] == 1:
			for i,button in enumerate(buttonlist):
				intvarlist[i].set(0)
		statusLabel.configure(foreground="blue")
		statvar.set("Status: Idle")
		barvar.set(0)
		for i,button in enumerate(buttonlist):
			button.config(state=NORMAL)
		sendButton.config(state=NORMAL)
		
def send():
	_thread.start_new_thread(send_thread,())

def clear():
	for i,button in enumerate(buttonlist):
		button.deselect()

def clear_after_timeout():
	if config['Clear after timeout']==True and config['Clear selection timeout'] > 0:
		if time.time()-last_select_time > config['Clear selection timeout']:
			clear()

def set_last_select_time():
	global last_select_time
	last_select_time = time.time()
	root.after(round((config['Clear selection timeout']+.2)*1000), clear_after_timeout)

def settingsmenu():
	sidetone = config['Sidetone']
	alerttone = config['Alert tone']
	clearduringsend = config['Clear during send']
	clearaftersend = config['Clear after send']
	clearaftertimeout = config['Clear after timeout']
	busychannellockout = config['Busy Channel Lockout']
	def disable_event():
		pass
	def save(junk):
		global config
		config['Radio Volume'] = radioVolume.get()
		config['Sidetone'] = sidetone
		config['Alert tone'] = alerttone
		config['Clear during send'] = clearduringsend
		config['Clear after send'] = clearaftersend
		config['Clear after timeout'] = clearaftertimeout
		config['Busy Channel Lockout'] = busychannellockout
		config['Busy Channel Lockout Debounce'] = bclDebounce.get()
		config['Clear selection timeout'] = clearTimeout.get()
		config['Radio Audio Output Index'] = output_device_indices[radio_output_device.get()]
		config['Sidetone Audio Output Index'] = output_device_indices[sidetone_output_device.get()]
		f = open('config.json','w')
		json.dump(config,f,indent=2)
		f.close()
	def change_audio_output(junk):
		save(0)
		radiostream.close()
		sidetonestream.close()
		p.terminate()
		start_streams()
		
	def exit_menu():
		menu.destroy()
	def exit_to_desktop():
		root.destroy()
	def shutdown():
		if running_on_pi == True:
			subprocess.run(["sudo","shutdown","-h","now"])
	def updateButtonText():
		if sidetone == 0:
			sideToneButton['text'] = "Sidetone During Send is OFF"
		else:
			sideToneButton['text'] = "Sidetone During Send is ON"
		if alerttone == 0:
			alertToneButton['text']="Alert Tone After Send is OFF"
		else:
			alertToneButton['text']="Alert Tone After Send is ON"
		if clearduringsend == 0:
			clearDuringSendButton['text'] = "Clearing Tone Selections During Send is OFF"
		else:
			clearDuringSendButton['text'] = "Clearing Tone Selections During Send is ON"
		if clearaftersend == 0:
			clearAfterSendButton['text']="Clearing Tone Selections After Send is OFF"
		else:
			clearAfterSendButton['text']="Clearing Tone Selections After Send is ON" 
		if clearaftertimeout== 0:
			clearAfterTimeoutButton['text']="Clearing Tone Selections After Inactivity is OFF"
			clearTimeout.grid_remove()
			clearTimeoutLabel.grid_remove()
		else:
			clearAfterTimeoutButton['text']="Clearing Tone Selections After Inactivity is ON" 
			clearTimeout.grid()
			clearTimeoutLabel.grid()
		if busychannellockout == 0:
			bclButton['text'] = "Busy Channel Lockout (BCL) is OFF"
			bclDebounce.grid_remove()
			bclLabel.grid_remove()
		else:
			bclButton['text'] = "Busy Channel Lockout (BCL) is ON"
			bclDebounce.grid()
			bclLabel.grid()
	def toggleSidetone():
		nonlocal sidetone
		sidetone = not sidetone
		updateButtonText()
		save(0)
	def toggleAlertTone():
		nonlocal alerttone
		alerttone = not alerttone
		updateButtonText()
		save(0)
	def toggleClearDuringSend():
		nonlocal clearduringsend
		clearduringsend = not clearduringsend
		updateButtonText()
		save(0)
	def toggleClearAfterSend():
		nonlocal clearaftersend
		clearaftersend = not clearaftersend
		updateButtonText()
		save(0)
	def toggleClearAfterTimeout():
		nonlocal clearaftertimeout
		clearaftertimeout = not clearaftertimeout
		updateButtonText()
		save(0)
	def toggleBCL():
		nonlocal busychannellockout
		busychannellockout = not busychannellockout
		updateButtonText()
		save(0)
	def changePin():
		settingspin('new')
	
	radio_output_device = StringVar()
	sidetone_output_device = StringVar()
	output_devices = []
	output_device_indices = {}
	#FIND THE AUDIO DEVICES ON THE SYSTEM
	info = p.get_host_api_info_by_index(0)
	numdevices = info.get('deviceCount')

	#find index of pyaudio input and output devices
	for i in range (0,numdevices):
		if p.get_device_info_by_host_api_device_index(0,i).get('maxOutputChannels')>0:
			output_devices.append(p.get_device_info_by_host_api_device_index(0,i).get('name'))
			output_device_indices[p.get_device_info_by_host_api_device_index(0,i).get('name')] = i
			inv_output_device_indices = dict((v,k) for k,v in output_device_indices.items())
	#p.terminate()
	radio_output_device.set(inv_output_device_indices.get(config['Radio Audio Output Index'],output_devices[0]))
	sidetone_output_device.set(inv_output_device_indices.get(config['Sidetone Audio Output Index'],output_devices[0]))
	
	menu = Toplevel()
	#menu.protocol("WM_DELETE_WINDOW", disable_event)
	menu.title('Settings')
	menu.geometry("400x750+800+25")
	# Make topLevelWindow remain on top until destroyed, or attribute changes.
	menu.attributes('-topmost', 'true')
	Label(menu,text = 'Radio Audio Output Device').grid(row = 0,column = 1,sticky="w",padx=10)
	OptionMenu(menu,radio_output_device,*output_devices,command = change_audio_output).grid(row = 1,column = 1,sticky = E+W)
	
	Label(menu,text = 'Sidetone Audio Output Device').grid(row = 2,column = 1,sticky="w",padx=10)
	OptionMenu(menu,sidetone_output_device,*output_devices,command = change_audio_output).grid(row = 3,column = 1,sticky = E+W)
	
	Label(menu,text="Transmit Audio Level: ").grid(row=7,column=1,sticky="w",padx=10)
	radioVolume = Scale(menu,from_=0, to=100, length=200,width=20,orient=HORIZONTAL,showvalue=1,highlightthickness=0,command=save)
	radioVolume.grid(row=8,rowspan = 1, column=1,pady=(0,10),sticky="w",padx=10)
	sideToneButton = Button(menu,text="Turn On Sidetone During Send",command=toggleSidetone,width=40)
	sideToneButton.grid(row=10,column=1,sticky="ew",padx=10,pady=5)
	alertToneButton = Button(menu,text="Turn On Alert Tone After Send",command=toggleAlertTone,width=40)
	alertToneButton.grid(row=12,column=1,sticky="ew",padx=10,pady=5)
	clearDuringSendButton = Button(menu,text="Clearing Tone Selections During Send is OFF",command=toggleClearDuringSend,width=30)
	clearDuringSendButton.grid(row=14,column=1,sticky="ew",padx=10,pady=5)
	clearAfterSendButton = Button(menu,text="Clearing Tone Selections After Send is OFF",command=toggleClearAfterSend,width=40)
	clearAfterSendButton.grid(row=16,column=1,sticky="ew",padx=10,pady=5)
	clearAfterTimeoutButton = Button(menu,text="Clearing Tone Selections After Inactivity is OFF",command=toggleClearAfterTimeout,width=40)
	clearAfterTimeoutButton.grid(row=18,column=1,sticky="ew",padx=10,pady=5)
	clearTimeoutLabel = Label(menu,text="Clear Selections After Inactivity (Sec):")
	clearTimeoutLabel.grid(row=20,column=1,sticky="w",padx=5)
	clearTimeout = Scale(menu,from_=0, to=60, length=200,width=20, resolution = 1,orient=HORIZONTAL,showvalue=1,highlightthickness=0,command=save)
	clearTimeout.grid(row=22, column=1,pady=(0,10),sticky="w",padx=10)
	
	bclButton = Button(menu,text="Busy Channel Lockout (BCL) is OFF",command=toggleBCL,width=40)
	bclButton.grid(row=24,column=1,sticky="ew",padx=10,pady=5)
	
	bclLabel = Label(menu,text="BCL Debounce Time (Sec):")
	bclLabel.grid(row=26,column=1,sticky="w",padx=5)
	bclDebounce = Scale(menu,from_=0, to=10, length=200,width=20,resolution = .1,orient=HORIZONTAL,showvalue=1,highlightthickness=0,command=save)
	bclDebounce.grid(row=28, column=1,pady=(0,10),sticky="w",padx=10)
	changePinButton = Button(menu,text="Change Settings PIN",command=changePin,width=40)
	changePinButton.grid(row=30,column=1,sticky="ew",padx=10,pady=5)
	desktopButton = Button(menu,text="Exit to Desktop",command=exit_to_desktop,width=40)
	desktopButton.grid(row=32,column=1,sticky="ew",padx=10,pady=5)
	if running_on_pi == True:
		shutdownButton = Button(menu,text="Shutdown System",command=shutdown,width=40)
		shutdownButton.grid(row=34,column=1,sticky="ew",padx=10,pady=5)
	exitButton = Button(menu,text="Exit Settings Menu",command=exit_menu,width=40)
	exitButton.grid(row=36,column=1,sticky="ew",padx=10,pady=5)
	
	radioVolume.set(config['Radio Volume'])
	updateButtonText()
	clearTimeout.set(config['Clear selection timeout'])
	bclDebounce.set(config['Busy Channel Lockout Debounce'])

def settingspin(entry_type='enter'):
	global config
	pin_menu = Toplevel()
	pin_menu.title('Enter PIN')
	pin_menu.geometry("+500+250")
	pin_text = StringVar()
	def check_pin():
		global new_pin
		if entry_type == 'enter':
			if pin_text.get() == config['Settings PIN']:
				settingsmenu()
				pin_menu.destroy()
		elif entry_type == 'new' and len(pin_text.get()) == 5:
			config['Settings PIN'] = pin_text.get()
			f = open('config.json','w')
			json.dump(config,f,indent=2)
			f.close()
			pin_menu.destroy()
	def check_length():
		if entry_type=='new':
			if len(pin_text.get())==5:
				enterButton['state'] = 'normal'
			else:
				enterButton['state']= 'disabled'
	def clear_pin():
		pin_text.set("")
		check_length()
	def append_zero():
		pin_text.set(pin_text.get() + "0")
		check_length()
	def append_one():
		pin_text.set(pin_text.get() + "1")
		check_length()
	def append_two():
		pin_text.set(pin_text.get() + "2")
		check_length()
	def append_three():
		pin_text.set(pin_text.get() + "3")
		check_length()
	def append_four():
		pin_text.set(pin_text.get() + "4")
		check_length()
	def append_five():
		pin_text.set(pin_text.get() + "5")
		check_length()
	def append_six():
		pin_text.set(pin_text.get() + "6")
		check_length()
	def append_seven():
		pin_text.set(pin_text.get() + "7")
		check_length()
	def append_eight():
		pin_text.set(pin_text.get() + "8")
		check_length()
	def append_nine():
		pin_text.set(pin_text.get() + "9")
		check_length()
		
	mainLabel = Label(pin_menu,text="Enter PIN to Access Settings",font=("Helvetica",14))
	mainLabel.grid(row=1,columnspan=4,padx=5)
	pinEntry = Entry(pin_menu,textvariable=pin_text)
	pinEntry.grid(row=2,columnspan=4,pady=5)
	oneButton = Button(pin_menu,text="1",command=append_one,width=10,height=3)
	oneButton.grid(row=3,column=1,padx=5,pady=5)
	twoButton = Button(pin_menu,text="2",command=append_two,width=10,height=3)
	twoButton.grid(row=3,column=2,padx=5,pady=5)
	threeButton = Button(pin_menu,text="3",command=append_three,width=10,height=3)
	threeButton.grid(row=3,column=3,padx=5,pady=5)
	fourButton = Button(pin_menu,text="4",command=append_four,width=10,height=3)
	fourButton.grid(row=5,column=1,padx=5,pady=5)
	fiveButton = Button(pin_menu,text="5",command=append_five,width=10,height=3)
	fiveButton.grid(row=5,column=2,padx=5,pady=5)
	sixButton = Button(pin_menu,text="6",command=append_six,width=10,height=3)
	sixButton.grid(row=5,column=3,padx=5,pady=5)
	sevenButton = Button(pin_menu,text="7",command=append_four,width=10,height=3)
	sevenButton.grid(row=7,column=1,padx=5,pady=5)
	eightButton = Button(pin_menu,text="8",command=append_five,width=10,height=3)
	eightButton.grid(row=7,column=2,padx=5,pady=5)
	nineButton = Button(pin_menu,text="0",command=append_six,width=10,height=3)
	nineButton.grid(row=7,column=3,padx=5,pady=5)
	clearButton = Button(pin_menu,text="Clear",command=clear_pin,width=10,height=3)
	clearButton.grid(row=9,column=1,padx=5,pady=5)
	zeroButton = Button(pin_menu,text="0",command=append_zero,width=10,height=3)
	zeroButton.grid(row=9,column=2,padx=5,pady=5)
	enterButton = Button(pin_menu,text="Enter",command=check_pin,width=10,height=3)
	enterButton.grid(row=9,column=3,padx=5,pady=5)
	if entry_type == 'new':
		enterButton['state']='disabled'
		mainLabel['text'] = 'Enter new 5 digit PIN'

def open_settings():
	if 'Settings PIN' in config:
		settingspin()
	else:
		settingsmenu()

def start_streams():
	global p, radiostream, sidetonestream, BITRATE
	BITRATE = 44100
	p = pyaudio.PyAudio()
	radiostream = p.open(
		format=pyaudio.paInt16,
		channels=1,
		rate=int(BITRATE),
		output=True,
		output_device_index = config['Radio Audio Output Index'])
	radiostream.start_stream()
		
	sidetonestream = p.open(
		format=pyaudio.paInt16,
		channels=1,
		rate=int(BITRATE),
		output=True,
		output_device_index = config['Sidetone Audio Output Index'])
	sidetonestream.start_stream()
start_streams()

#-- GUI LAYOUT --
root = Tk()
'''
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
print(screen_width)
print(screen_height)
'''
root.geometry("1280x800")
root.title('Paging Encoder')
#root.iconbitmap('icon.ico')
root.configure(background='black')
root.wm_attributes('-fullscreen','true')
f = Frame(bd=10)
f.configure(background='black')
f.grid(row = 1,column=1)
f2 = Frame(bd=10)
f2.configure(background='black')
f2.grid(row=1,column=2,rowspan=20,sticky='ns')
f3 = Frame(bd=20)
f3.configure(background='black')
f3.grid(row=2,column=1,columnspan=2,sticky='sew')

intvarlist = []
buttonlist = []
barvar = IntVar()
statvar = StringVar()
statvar.set("Status: IDLE")
def saveSidetoneVolume(junk):
	config['Sidetone Volume'] = sidetoneVolume.get()
for i, tone in enumerate(tones['Tones']):
	#Label(f,text=tone['description'],font=("Helvetica",12)).grid(row=row,column=1,sticky = W)
	#https://anzeljg.github.io/rin2/book2/2405/docs/tkinter/checkbutton.html
	intvarlist.append(IntVar())
	buttonlist.append(Checkbutton(f,text=tone['description'],variable=intvarlist[i],command=set_last_select_time,selectcolor="yellow",indicatoron=0,width=25,height=2,font=("Helvetica",24)))
	col = i//6
	if col%2==0:
		#even number colums
		sticky ="E"
	else:
		sticky = "W"
	buttonlist[i].grid(row=i%6,column=i//6,sticky =sticky,pady=10,padx=15)

sendButton = Button(f2,text="SEND",command=send,font=("Helvetica",24),width=10,height=2)
sendButton.grid(row=0,column=1,pady=10,padx=15)
clearButton = Button(f2,text="CLEAR",command=clear,font=("Helvetica",24),width=10,height=2)
clearButton.grid(row=2,column=1,pady=10,padx=15)
Label(f2,text="",background='black',height=10).grid(row=3,rowspan=2)
Label(f2,text="Sidetone Volume",background='black',foreground='white').grid(row=5,column=1)
sidetoneVolume = Scale(f2,from_=0, to=100, tickinterval=100,orient=HORIZONTAL,showvalue=1,background='black',foreground='white',highlightthickness=0,length=200,command=saveSidetoneVolume)
sidetoneVolume.grid(row=8,column=1)
sidetoneVolume.set(config['Sidetone Volume'])
settingsButton = Button(f2,text="Settings",command=open_settings,font=("Helvetica",24),width=10,height=1)
settingsButton.grid(row=9,column=1,pady=10,padx=15)

statusLabel = Label(f3,textvar = statvar,font=("Helvetica", 24),background='black',foreground='blue')
statusLabel.grid(row = 1, column = 0,columnspan = 4,sticky = "w")
progress = ttk.Progressbar(f3, orient = HORIZONTAL, length = 1240,variable = barvar)
progress.grid(row=2,column=0,columnspan=4,sticky="ew")

#-- END GUI LAYOUT --

root.mainloop()
