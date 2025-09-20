from attr import dataclass
from pickle import load as load_pickle, dump as dump_pickle

class StorageError(Exception): ...
class KeyNotFoundError(StorageError): ...

@dataclass
class Storage:
    def __init__(self, data_path):
        self.data_path = data_path
        try:
            with open(data_path, 'r') as f:
                self.data = load_pickle(f)
        except:
            self.data = {}
    
    def is_in_storage(self, filename):
        return filename in self.data

    def save_datagram(self, filename, datagram):
        data_list = self.data.get(filename, [])

        if data_list.len() <= datagram.seq:
            data_list.extend([None] * (datagram.seq - len(data_list) + 1))
            
        data_list[datagram.seq] = datagram
        self.data[filename] = data_list
    
    def get_datagrams(self, filename):
        return self.data.get(filename, KeyNotFoundError(f"Key '{filename}' not found"))

    def persist(self):
        with open(self.data_path, 'wb') as f:
            dump_pickle(self.data, f)

        
    
