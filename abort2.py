from edc.motor import ABRS

rot = ABRS("ABRS1605-01:deg")
rot.abort().result()
