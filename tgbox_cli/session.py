from tgbox.crypto import AESwState as AES

from typing import Optional
from pickle import loads, dumps

from hashlib import sha256
from pathlib import Path

from .tools import get_cli_folder


class Session:
    """
    This class serves as a simple implementation of
    Session to save & load state. All you need is
    specify the so-called SessionKey and it will
    be used to encrypt any committed data.
    """
    def __init__(self, key: str, folder: Optional[Path] = None):
        if not key:
            raise ValueError('key can not be empty')

        if not folder:
            folder = get_cli_folder()

        self.folder, self.key = folder, key
        self.enc_key = sha256(key.encode()).digest()

        self.file = folder / f'sess_{sha256(self.enc_key).hexdigest()}'
        try:
            state = open(self.file,'rb').read()
            self.state = loads(AES(self.enc_key).decrypt(state))
        except FileNotFoundError:
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
