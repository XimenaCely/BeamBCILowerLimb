# BeamBCI setup

## Prerequisites

**Windows**

* Install the latest Microsoft Visual C++ 2015-2022 package for the x64 architecture. Even if you run Windows on ARM, install the x64 version. 
You can always download the latest version here: [Microsoft Download page](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170)

**Linux**

* Make sure liblsl is installed on your computer. Debian packages for x64 and arm64 are available via the [liblsl Github releases section](https://github.com/sccn/liblsl/releases/). 
On Linux distributions not supporting Debian packages you might need to compile liblsl yourself. This usually works very well, helpful instructions are available in the 
[liblsl documentation](https://labstreaminglayer.readthedocs.io/dev/lib_dev.html#configuring-the-liblsl-project).

**MacOS**

* Make sure liblsl is installed. You can install e.g. via brew: `brew install labstreaminglayer/tap/lsl`

## BeamBCI installation

1. Download or clone the BeamBCI repository

2. Ensure Python 3.11 or newer is installed on your computer. 
To check its availability and version, open a terminal / command prompt and type `python -V` 
(depending on your operating system you might need to type `python3 -V` or `python.exe -V`)

3. Update your python's HTTPS certificates by typing `python -m pip install --upgrade certifi`

4. Close and reopen your terminal to make the recent updates available in the new session.

5. In the terminal, navigate (`cd`) into the BeamBCI directory and run `python setup/beambci_setup.py`. 
