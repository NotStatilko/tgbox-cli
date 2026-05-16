"""
Encrypted (by TGBOX_CLI_SK key) Session class that is
used to store your Box keys per terminal.
"""

from typing import Optional
from tempfile import gettempdir
from json import loads, dumps

from base64 import urlsafe_b64encode
from hashlib import sha256
from hmac import HMAC, compare_digest
from pathlib import Path

from ..config import tgbox
if hasattr(tgbox, 'crypto'):
    AES = tgbox.crypto.AESwState
else:
    # Autocompletion will create dummy tgbox object
    # to omit useless imports. As AES will not be
    # used in actual code, we can just set it to
    # the None value.
    AES = None


class Session:
    """
    This class serves as a simple implementation of
    Session to save & load state. All you need is
    specify the so-called SessionKey and it will
    be used to encrypt any committed data.
    """
    def __init__(self, session_key: str, folder: Optional[Path] = None):
        """
        Arguments:
            session_key: str:
                In TGBOX-CLI, session key is a Key that
                we store in $TGBOX_CLI_SK env var. We
                use it to generate session Enc key.

            folder: Path, optional:
                Folder is a directory where session
                file will be stored. By default, it's
                <TEMP>/.tgbox-cli directory
        """
        if not session_key:
            raise ValueError('session_key can not be empty')

        if not folder:
            folder = Path(gettempdir()) / '.tgbox-cli'

        folder.mkdir(exist_ok=True, parents=True)
        try:
            if folder.stat().st_mode != 16895: # oct(16895) is 0o777
                # Allow different users to store
                # sessions in this folder (UNIX)
                folder.chmod(0o777)
        except PermissionError:
            pass # We can not change permissions from this user.
                 # This shouldn't be a problem, as initial user
                 # (creator) of this folder should set it to 777

        self.folder, self.session_key = folder, session_key
        self.enc_key = sha256(session_key.encode()).digest()

        session_id = sha256(session_key.encode() + self.enc_key)
        session_id = urlsafe_b64encode(session_id.digest()[:18])

        self.file = folder / f'sess_1_{session_id.decode()}'
        try:
            encrypted_state = open(self.file,'rb').read()
            if not encrypted_state:
                raise FileNotFoundError

            hmac_f = encrypted_state[-32:]
            encrypted_state = encrypted_state[:-32]

            hmackey = HMAC(b'hmac+' + self.enc_key, digestmod='sha256')
            hmackey.update(encrypted_state)

            if not compare_digest(hmackey.digest(), hmac_f):
                self.file.unlink()

                raise ValueError(
                    'Session file is broken and/or was tampered with! We will '
                    'remove your current session. Please, try again. Reset your '
                    'TGBOX_CLI_SK env var!! Open tgbox-cli in new Terminal.'
                )

            self.state = loads(AES(self.enc_key).decrypt(encrypted_state))

        except FileNotFoundError:
            self.file.touch()      # chmod is effectively ignored by Windows, so
            self.file.chmod(0o600) # this basically works only on a POSIX-like
                                   # machines. Blame shitty Windows for this.
            self.state = {
                'BOX_LIST': [],
                'CURRENT_BOX': None,

                'ACCOUNT_LIST': [],
                'CURRENT_ACCOUNT': None
            }

    def __getitem__(self, slice_: slice):
        return self.state[slice_]

    def __setitem__(self, key, value):
        self.state[key] = value

    def __delitem__(self, key):
        del self.state[key]

    def __repr__(self):
        return f'{self.state=}'

    def commit(self):
        """Will write changes made to self.state to file in encrypted form"""
        state_data = dumps(self.state, separators=(',',':')).encode()
        encrypted_state = AES(self.enc_key).encrypt(state_data)

        hmackey = HMAC(b'hmac+' + self.enc_key, digestmod='sha256')
        hmackey.update(encrypted_state)
        encrypted_state += hmackey.digest()

        open(self.file,'wb').write(encrypted_state)
