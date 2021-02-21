from concert.devices.cameras.uca import Camera as UcaCamera
from edc.motor import CLSLinear
from concert.processes.common import focus

print("import")
camera = UcaCamera("pco")
print("Cam")
f_motor = CLSLinear("SMTR1605-2-B10-13:mm", encoded=False)

def main(camera, f_motor):
    print("start position: {}".format(f_motor.position))
    focus(camera, f_motor).join()
    print("end position: {}".format(f_motor.position))

if __name__ == "__main__":
    main(camera, f_motor)
