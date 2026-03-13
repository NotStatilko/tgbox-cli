# A *C*ommand *L*ine *I*nterface to the TGBOX

This is a [**CLI**](https://en.wikipedia.org/wiki/Command-line_interface) implementation of the [**TGBOX**](https://github.com/NonProjects/tgbox/) — an encrypted cloud storage built around the [**Telegram**](https://telegram.org). 

**TGBOX-CLI** supports all features of the `tgbox` protocol, adding additional ones\
like basic **Encrypted Chat** and support for **unlimited file size** (4GB+) uploads.

![List of the TGBOX-CLI commands](https://github.com/user-attachments/assets/85039ac8-80c7-4cf3-a86d-0912100cdd7e)
## Installation

### Install with PIP

If you have **Python 3** on your machine, you can install latest *stable* release of the ``tgbox-cli`` from [PyPI](https://pypi.org/project/tgbox-cli):
```bash
# Drop [fast] to obtain *slow*, pure-Python build
pip install -U tgbox-cli[fast]
```

### Clone & Install

Alternatively, you can **clone this repository** and install from the source. This may give you more control over the code:
```bash
python -m venv tgbox-cli-env
cd tgbox-cli-env && . bin/activate

git clone https://github.com/NotStatilko/tgbox-cli
pip install ./tgbox-cli[fast]
```
### Builds

We provide [**GitHub actions repository**](https://github.com/NotStatilko/tgbox-cli-build/releases) designed specifically to build the `tgbox-cli` executables. You\
can either get your builds there, of consult the **Manual Build** chapter.

#### Manual Build

To build `tgbox-cli`, you need to have at least **Python 3.9** installed on your machine. It is *not* required, but we use **FFmpeg** to **make previews** and **extract duration of media files**. If you want your executable to support these features, — you **should** download `ffmpeg` executable and place it in *specific directory* before build. We have [**GitHub Actions repository**](https://github.com/NotStatilko/ffmpeg-preview/releases) that is created *specifically* for building the minimal **FFmpeg** executables. You can either use them **(recommended)**, *or* download a build for your machine **from official FFMpeg website**.  

```bash
python -m venv tgbox-cli-env
cd tgbox-cli-env && . bin/activate

pip install pyinstaller

git clone https://github.com/NonProjects/tgbox
cd tgbox/tgbox/other # Place ffmpeg executable here

cd ../../.. # Move back

git clone https://github.com/NotStatilko/tgbox-cli
pip install ./tgbox-cli

pip install ./tgbox[fast]

cd tgbox-cli/pyinstaller
pyinstaller tgbox_cli.spec

# Run the executable and show info
dist/tgbox-cli cli-info 
```
**Please note** that You can also set `TGBOX_CLI_NON_ONEFILE` env variable to build without packing\
into one executable file. You can freely remove the ``tgbox-cli-env`` folder after build is complete.

## Usage

TGBOX-CLI is your typical Command-Line application. You can run it just by typing executable name in Terminal:
```bash
tgbox-cli
```
This should return you a list of **commands**. The **help** command will give you a full course over **TGBOX-CLI**.\
Use it (as well as ``--help`` *option* on every **command**) if you don't know anything about this application:
```bash
tgbox-cli help
```

## Bug reports

Feel free to **report some bugs** (I believe there can be many) on the [**GitHub Issue tab**](https://github.com/NotStatilko/tgbox-cli/issues). Any encountered error should be written to the logfile. Use the **logfile-open** command and **attach** its contents to the bug report **(make sure nothing private is in there)**.

**Thanks**.
