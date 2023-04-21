# A *C*ommand *L*ine *I*nterface to the TGBOX

**Hi!** This is a [**CLI**](https://en.wikipedia.org/wiki/Command-line_interface) implementation of the [**TGBOX**](https://github.com/NonProjects/tgbox/) — an encrypted cloud storage built around the [**Telegram**](https://telegram.org).

## A quick install

This project is still *in development* and some features can be changed at *any time*.\
The best way you can choose if you want to test it right now, — it's use source code:
```
python3 -m venv tgbox-cli-env
cd tgbox-cli-env && . bin/activate

git clone https://github.com/NonProjects/tgbox --branch=indev
pip install ./tgbox[fast]

git clone https://github.com/NotStatilko/tgbox-cli
pip install ./tgbox-cli[fast]

tgbox-cli
```
Feel free to report some things on the GitHub Issue tab &\
make sure to `git pull` and reinstall projects on updates.
