from epics import caput

caput("ABRS1605-01:cmd:abort", 1)
caput("ABRS1605-01:cmd:home", 1)