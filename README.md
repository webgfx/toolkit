# Get the code
git clone --recursive https://github.com/webgfx/toolkit.git

# Work with GN project
cd misc && python3 gnp.py --sync --runhooks --makefile --build --backup --build-target=xxx --root-dir=xxx

# TODO
bisect mesa, webmark, angle, aosp, chromeos, dawn, skia, v8
how to port performance test, how to port webgl-cts
