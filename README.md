
## Update 2023-01-06

My AX1200i finally gave up the ghost, probably due to lightning. Unless I'm able to fix it (unlikely), I won't be able to continue this.

I'll leave this up in case anyone else wants to pick it up.

# Work-in-progress liquidctl driver for AX1200i

For now, works on linux only, but that's only because of how the serial port is opened.

If you want to try on your platform, replace /dev/serial... with the correct serial port of your PSU.

Should in theory work with AX1500i, AX1200i, AX860i, AX760i. Tested only with AX1200i.

If imported as a module in ipython, you can set fan settings. That works well.

TODO: 
 * 12V rails on other PSUs
 * Convert from pySerial to pyUSB. Should improve speed.

ISSUES:
 * Slow. Probably due to waiting on serial port.
 * 12V rails are very slow, seems like the PSU might be to blame
 * Sometimes data is 0.
 * Efficiency is sometimes reported above 100% due to inaccurate estimated input power.
