from datetime import date
from datetime import datetime
from datetime import timedelta
import gspread
import time
import sys
import RPi_I2C_driver
from pygame import mixer

#set the display
display = RPi_I2C_driver.lcd()
#display a welcome message (clear has to happen first in case there's any lingering message on-screen)
display.lcd_clear()
display.lcd_display_string("Drinkup Online!", 1)

#turns on the sound mixer
mixer.init()

#we've got a real scale, don't emulate it
EMULATE_HX711=False
#not setting a reference unit because we don't need to actually know what the cup weighs in any particular unit
referenceUnit = 1

#sets the variables for the sounds we'll be using
boot = mixer.Sound('applause-1.wav') #applause sfx
cup1 = mixer.Sound('applause-1.wav') #congrats on drinking one
cup2 = mixer.Sound('applause-1.wav') #congrats for 2
cup3 = mixer.Sound('applause-1.wav') #congrats for 3
cup4 = mixer.Sound('applause-1.wav') #congrats for 4
cup5 = mixer.Sound('applause-1.wav') #congrats for 5
cup6 = mixer.Sound('applause-1.wav') #generic congrats (stop counting after 5)
reminder = mixer.Sound('applause-1.wav') #it's been 2 hours since your last drink, get to it

#sets google sheets creds/specifics/connects
gc = gspread.service_account(filename='client_secret.json') #grabs google creds
sh = gc.open_by_key('1RJE7y-R-vo8tHT6j0NmHjJBKwhMT_C7s08D8MEL8fUM') #specifies what sheet to open by key
worksheet = sh.sheet1 #specifices the worksheet (there's only 1 anyway)

#get initial sheets values
totalrows=len(worksheet.col_values(1)) #makes the variable a equal to the number of rows in the first column
lastrowval = worksheet.cell(totalrows, 1).value #reads the value of the last row in the first column
newrow = totalrows+1 #if I need to make a new row at the bottom of the sheet, this is the row number
today = date.today() #grabs today's date
lastweightime = datetime.now() #grabs current timestamp
lastcuptime = lastweightime - timedelta(seconds=601) #I've placed a 10 minute hold period between weighing a new cup, effectively to avoid putting the same empty cup on multiple times. This initializes that timer, but starts it at more than 10 minutes ago so a cup can be weighed as soon as Drinkup tares.
lastcuptimestring = str(lastcuptime)
todaystring = str(today) #converts the date to a string
cupsdrank = 0 #variable to track how many cups have been drank today
cupsdrankstring = str(cupsdrank)
cuponthescale = 0 #assumes there is no cup on the scale at time of tare - this is used so that if Ash leaves a cup on the scale for more than 10 minutes, he doesn't keep getting artificial drink$
lastdrink = datetime.now()

if (lastrowval == todaystring): #on boot, checks if there's already a Gsheet record for today
    print("row exists for today")
    cupsonboot = worksheet.cell(totalrows, 2).value #reads the value of the cups drank in the last updated row on boot
    print(cupsonboot)
    cupsdrankstring = cupsonboot #updates the cupsdrankstring value to match what's there currently in case the machine was turned off mid-day
    cupsdrank = int(cupsdrankstring) #converts that cupsdrankstring value to an integer
    print(cupsdrank)
    cupsdrankstring = str(cupsdrank)
else: #if there's not a row for today, makes one
    worksheet.update_cell(newrow, 1, todaystring)
    worksheet.update_cell(newrow, 2, cupsdrankstring)

#actually turn on the scale
if not EMULATE_HX711:
    import RPi.GPIO as GPIO
    from hx711 import HX711
else:
    from emulated_hx711 import HX711

#function that cleans up the scale hardware memory when the program ends
def cleanAndExit():
    print("Cleaning...")

    if not EMULATE_HX711:
        GPIO.cleanup()
        
    print("Bye!")
    sys.exit()

def lcdCupsDrank(): #prints how many cups drank so far to lcd screen
    display.lcd_clear()
    display.lcd_display_string("Cups Drank:", 1) #prints this to first row
    display.lcd_display_string(cupsdrankstring, 2) #prints this to second row of lcd

def cupSound(): #plays a sound based on how many cups have been drank yet
    if (cupsdrank == 1):
        cup1.play()
    elif (cupsdrank == 2):
        cup2.play()
    elif (cupsdrank == 3):
        cup3.play()
    elif (cupsdrank == 4):
        cup4.play()
    elif (cupsdrank == 5):
        cup5.play()
    elif (cupsdrank > 5):
        cup6.play()
    else:
        print("No cups drank yet, why would there be a sound here?")

#defines the raspberry pi pins for the scale
hx = HX711(7, 11)

# I've found out that, for some reason, the order of the bytes is not always the same between versions of python, numpy and the hx711 itself.
# Still need to figure out why does it change.
# If you're experiencing super random values, change these values to MSB or LSB until to get more stable values.
# There is some code below to debug and log the order of the bits and the bytes.
# The first parameter is the order in which the bytes are used to build the "long" value.
# The second paramter is the order of the bits inside each byte.
# According to the HX711 Datasheet, the second parameter is MSB so you shouldn't need to modify it.
hx.set_reading_format("MSB", "MSB")

display.lcd_clear()
display.lcd_display_string("Taring now!", 1)

# HOW TO CALCULATE THE REFFERENCE UNIT (I'm not doing this right now - don't actually need to know what the cup weighs in any specific unit for the moment, keeping these notes here in case I change my mind.)
# To set the reference unit to 1. Put 1kg on your sensor or anything you have and know exactly how much it weights.
# In this case, 92 is 1 gram because, with 1 as a reference unit I got numbers near 0 without any weight
# and I got numbers around 184000 when I added 2kg. So, according to the rule of thirds:
# If 2000 grams is 184000 then 1000 grams is 184000 / 2000 = 92.
#hx.set_reference_unit(113)
hx.set_reference_unit(referenceUnit)

#clears any data left in the scale, then tares the scale
hx.reset()
hx.tare()
print("Tare done! Add weight now...")
display.lcd_clear()
display.lcd_display_string("Tare complete!", 1) #print message to LCD saying the Tare is done
boot.play() #plays the boot sound
time.sleep(1)
lcdCupsDrank()

while True:
    try:        
        # Prints the weight. Comment if you're debbuging the MSB and LSB issue.
        scaleweight = hx.get_weight(5)
        print(scaleweight)
        rightnow = datetime.now()
        timesince = rightnow-lastweightime
        cuptimesince = rightnow-lastcuptime

        if(scaleweight > 200):
            if(scaleweight > 19599): #if weight is more than totally empty cup
                if(scaleweight < 41801): #but less than a cup with water in it
                    if(cuponthescale == 0): #are we sure this isn't just one empty cup that Ash left on the scale?
                        if (cuptimesince.seconds > 600): #has it been 10 minutes since we finished a cup last?
                            cuponthescale = 1 #tells the scale there is a cup on the scale
                            cupsdrank += 1
                            cupsdrankstring = str(cupsdrank)
                            lastweightime = datetime.now()
                            lcdCupsDrank()
                            lastcuptime = datetime.now()
                            cupSound()
                            lastdrink = rightnow
                            totalrows=len(worksheet.col_values(1)) #makes the variable a equal to the number of rows in the first column
                            lastrowval = worksheet.cell(totalrows, 1).value #reads the value of the last row in the first column
                            newrow = totalrows+1
                            today = date.today() #grabs today's date
                            if (lastrowval != todaystring):
                                 worksheet.update_cell(newrow, 1, todaystring)
                                 worksheet.update_cell(newrow, 2, cupsdrankstring)
                            else:
                                 worksheet.update_cell(totalrows, 2, cupsdrankstring)
                        else:
                            print ("cup still on scale")
                    else:
                        lcdCupsDrank()
                        print("too soon")
                else: #reset the dim timer, even if it wasn't a cup
                    lastweightime = datetime.now()
                    lcdCupsDrank()
            else: #reset the dim timer, even if not a cup
                lastweightime = datetime.now()
                lcdCupsDrank()
        elif (timesince.seconds > 30): #after 30 seconds without the weight being touched, turn off the lcd backlight
            display.backlight(0)
        else: #sets cuponthescale to 0, meaning the empty cup has been removed
            cuponthescale = 0
            print(timesince.seconds)

        sincelastdrink = rightnow-lastdrink
        if (rightnow.hour > 10): #is it past 10AM EST?
            if (rightnow.hour < 20): #is it before 8PM EST
                print("the time is right for a reminder")
                if (sincelastdrink.seconds > 7199):
                    reminder.play()
                    lastdrink = rightnow
                else:
                    print ("we don't need a reminder yet")
            else:
                print("too late for a reminder")
        else:
                print("too early  to play reminder")

        print("The current hour is: ")
        print(rightnow.hour)

        possiblystilltoday = date.today() #what's today's date?
        if (today != possiblystilltoday): #has the date changed since the last try?
            cupsdrank = 0 #if so, it's a new day, no cups have been drank yet
            today = date.today() #update today
        else: #if not, don't do anything. print a message.
            print ("day hasn't changed")

        hx.power_down()
        hx.power_up()
        time.sleep(0.1)

    except (KeyboardInterrupt, SystemExit):
        display.lcd_clear()
        display.backlight(0)
        cleanAndExit()
