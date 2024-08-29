from tgbox.crypto import AESwState as AES

from typing import Optional
from tempfile import gettempdir
from pickle import loads, dumps

from base64 import urlsafe_b64encode
from hashlib import sha256
from pathlib import Path


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
            if folder.stat().st_size != 16895: # oct(16895) is 0o777
                # Allow different users to store
                # sessions in this folder (UNIX)
                folder.chmod(0o777)
        except PermissionError:
            pass # We can not change permissions from this user.
                 # This shoudln't be a problem, as initial user
                 # (creator) of this folder should set it to 777

        self.folder, self.session_key = folder, session_key
        self.enc_key = sha256(session_key.encode()).digest()

        session_id = sha256(session_key.encode() + self.enc_key)
        session_id = urlsafe_b64encode(session_id.digest()[:18])

        self.file = folder / f'sess_{session_id.decode()}'
        try:
            state = open(self.file,'rb').read()
            assert state, 'State is empty.'
            self.state = loads(AES(self.enc_key).decrypt(state))
        except (AssertionError, FileNotFoundError):
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
        encrypted_state = AES(self.enc_key).encrypt(dumps(self.state))
        open(self.file,'wb').write(encrypted_state)
