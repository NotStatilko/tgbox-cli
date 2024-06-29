# A *C*ommand *L*ine *I*nterface to the TGBOX

This is a [**CLI**](https://en.wikipedia.org/wiki/Command-line_interface) implementation of the [**TGBOX**](https://github.com/NonProjects/tgbox/) — an encrypted cloud storage built around the [**Telegram**](https://telegram.org).

![List of the TGBOX-CLI commands](https://github.com/NotStatilko/tgbox-cli/assets/43419673/b84b98e9-1ea1-432f-86d3-07a018d315bc)
## Installation

To *build* the **TGBOX-CLI** you will need to have **at least** Python 3.8.

### Windows builds (.EXE)

You can use already created executable builds if you're on Windows.\
See [**Releases GitHub page**](https://github.com/NotStatilko/tgbox-cli/releases) or navigate to the [**official TGBOX dev.channel**](https://t.me/nontgbox)

### Build the TGBOX-CLI

To make all features work, you will also need the [**FFmpeg**](https://ffmpeg.org/download.html) installed in your system (it should\
be also accessible by the simple ``ffmpeg`` command from your Terminal, in other words: in ``PATH``).

#### Install with PIP

You can install latest *stable* release of the ``tgbox-cli`` from [PyPI](https://pypi.org/project/tgbox-cli):
```bash
# Drop [fast] to obtain *slow*, pure-Python build
pip install -U tgbox-cli[fast]
```

#### Clone & Install

Alternatively, you can clone this repository and build from the source. This may give you more control over the code:
```bash
python -m venv tgbox-cli-env
cd tgbox-cli-env && . bin/activate

git clone https://github.com/NotStatilko/tgbox-cli
pip install ./tgbox-cli[fast]
```
#### PyInstaller

If you want to make your own .EXE build *with FFmpeg*, you *will need* to download\
it and place inside the ``tgbox/other`` directory (on Windows only). See this:
```bash
python -m venv tgbox-cli-env
cd tgbox-cli-env && . bin/activate

pip install pyinstaller

git clone https://github.com/NonProjects/tgbox
cd tgbox/tgbox/other # Make sure to place here ffmpeg.exe
```
(after you dropped the ``ffmpeg.exe`` to the ``tgbox/other``):
```bash
cd ../../.. # Move back
pip install ./tgbox[fast]

git clone https://github.com/NotStatilko/tgbox-cli
pip install ./tgbox-cli[fast]

cd tgbox-cli/pyinstaller
pyinstaller tgbox_cli.spec

# Run the executable and show info
dist/tgbox-cli.exe cli-info
```
**Please note** that You can also set `TGBOX_CLI_NON_ONEFILE` env variable to build without packing \
into one executable file & feel free to remove the ``tgbox-cli-env`` folder after work was done.

## Usage

The TGBOX-CLI is a typical Command-Line application. After install, it can be ran as follows:
```bash
tgbox-cli
```
This should output you a list of **commands**. The **help** command will give you a full course over **TGBOX-CLI**.\
Use it (as well as ``--help`` *option* on every **command**) if you don't know anything about this application:
```bash
tgbox-cli help
```

## Bug reports

Feel free to report some problems (i believe there can be many) on the [**GitHub Issue tab**](https://github.com/NotStatilko/tgbox-cli/issues). Any encountered error should be written to the logfile. Use the **logfile-open** command and **attach** its content to the bug report.

**Thanks**.
