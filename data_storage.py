import os, json
import inspect

from .mouse_position import MousePosition

class DirectoryRelative(Exception):
    pass

DEFAULT_MAX_BYTES = 50000000
class Storage:
    #Half a gigabyte
    def __init__(self, dir, *, max_bytes = DEFAULT_MAX_BYTES):
        if _directory_is_absolute_path(dir):
            self.dir = dir
        else:
            raise DirectoryRelative(dir)
        _create_directory_if_nonexistent(self.dir)
        self.max_bytes = max_bytes

    def position_file(self, name: str):
        return self.storage_file(name, MousePositionFile) 
    
    def integer_file(self, name: str):
        return self.storage_file(name, IntegerFile)
    
    def float_file(self, name: str):
        return self.storage_file(name, FloatFile)
    
    def string_file(self, name: str):
        return self.storage_file(name, StringFile)
    
    def boolean_file(self, name: str):
        return self.storage_file(name, BooleanFile)

    def json_file(self, name: str, from_json = None, *, default = None, cls = None, initial_value = None):
        return JSONFile(self.get_path(), name, from_json = from_json, default = default, cls = cls, 
        initial_value = initial_value)

    def storage_file(self, name: str, type):
        return type.create(self.get_path(), name, max_bytes = self.max_bytes)

    def get_path(self):
        return self.dir

def _create_directory_if_nonexistent(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def _directory_is_absolute_path(path):
    return os.path.isabs(path)

class RelativeStorage(Storage):
    def __init__(self, path, name = 'Fire Chicken Storage', *, max_bytes = DEFAULT_MAX_BYTES):
        target_directory = _compute_directory_at_path(path)
        dir = _join_path(target_directory, name)
        Storage.__init__(self, dir, max_bytes = max_bytes)

def _compute_directory_at_path(path):
    if os.path.isdir(path):
        return path
    else:
        return _compute_file_directory(path)

def _compute_file_directory(path):
    absolute_filepath = os.path.abspath(path)
    file_directory = os.path.dirname(absolute_filepath)
    return file_directory

def _join_path(directory, path):
    return os.path.join(directory, path)

#Parent class not meant to be instantiated
#Implement Python string method for storing object for storage
    #or override _convert_to_text
#Implement classmethod get_value_from_text for reading from the file
#Implement _initial_value for setting the initial value
class StorageFile:
    def __init__(self, folder: str, name: str, *, max_bytes: int = DEFAULT_MAX_BYTES):
        self.folder = folder
        self.name = name
        self.max_bytes = max_bytes
        self._initialize_file_if_nonexistent()
        self._retrieve_value()
    @classmethod
    def create(cls, folder: str, name: str, *, max_bytes: int = DEFAULT_MAX_BYTES):
        return cls(folder, name, max_bytes = max_bytes)


    def get(self):
        return self.value
    
    def set(self, value):
        self.value = value
        self._store_value()
    
    def _store_value(self):
        with open(self.get_path(), 'w') as value_file:
            value_text = self._convert_to_text()
            value_file.write(value_text)
    
    def _convert_to_text(self) -> str:
        return str(self.value)

    def _retrieve_value(self):
        if self._file_too_big():
            self._raise_file_too_big_exception()
        with open(self.get_path(), 'r') as position_file:
            value_text = position_file.read(self.max_bytes)
            self.value = self.get_value_from_text(value_text)

    def _file_too_big(self):
        file_size = os.path.getsize(self.get_path())
        return file_size > self.max_bytes

    def _raise_file_too_big_exception(self):
        raise InvalidFileSizeException(f'Storage file at path {self.get_path()} exceeded maximum size of'
        f'{self.max_bytes} bytes!'
        )

    def get_path(self):
        return os.path.join(self.folder, self.name)

    def _initialize_file_if_nonexistent(self):
        if self.exists():
            self.initialize()
    def exists(self):
        return not os.path.exists(self.get_path())
    def initialize(self):
        self._make_directory_if_nonexistent()
        initial_value = self._initial_value()
        self.set(initial_value)
    
    def _make_directory_if_nonexistent(self):
        _create_directory_if_nonexistent(self.folder)
    
    def delete(self):
        os.remove(self.get_path())

class JSONFile(StorageFile):
    def __init__(self, folder: str, name: str, *, max_bytes: int = DEFAULT_MAX_BYTES, initial_value = None, 
        default = None, cls = None, from_json = None):
        self.initial_value = initial_value
        self.default = default
        self.cls = cls
        self._raise_exception_if_invalid_argument_combination()
        self.object_from_json = JSONFile._get_from_json_function(from_json)
        StorageFile.__init__(self, folder, name, max_bytes = max_bytes)
    
    def _raise_exception_if_invalid_argument_combination(self):
        if self.default is not None and self.cls is not None:
            raise ValueError('JSONFile objects should not receive default and cls')

    @staticmethod
    def _get_from_json_function(from_json):
        if JSONFile._from_json_function_is_method(from_json):
            return JSONFile._get_from_json_function_from_class(from_json)
        else:
            return from_json
    @staticmethod
    def _from_json_function_is_method(from_json):
        return hasattr(from_json, 'from_json') and callable(from_json.from_json)
    @staticmethod
    def _get_from_json_function_from_class(classname):
        return lambda value : classname.from_json(value)

    def _convert_to_text(self) -> str:
        if self._encoder_function_provided():
            return self._encode_using_encoder_function()
        if self._encoder_class_provided():
            return self._encode_using_encoder_class()
        if self._value_has_encoder_method():
            return self._encode_using_encoder_method()
        return self._encode_using_json_default_encoding()

    def _encoder_function_provided(self):
        return self.default is not None
    def _encoder_class_provided(self):
        return self.cls is not None
    def _value_has_encoder_method(self):
        return hasattr(self.value, 'to_json') and callable(self.value.to_json)
    
    def _encode_using_encoder_function(self):
        return json.dumps(self.value, default = self.default)
    def _encode_using_encoder_class(self):
        return json.dumps(self.value, cls = self.cls)
    def _encode_using_encoder_method(self):
        return json.dumps(self.value.to_json())
    def _encode_using_json_default_encoding(self):
        return json.dumps(self.value)

    def get_value_from_text(self, text: str):
        json_value = json.loads(text)
        if self.object_from_json is None:
            return json_value
        return self.object_from_json(json_value)
    
    def _initial_value(self):
        return self.initial_value

class InvalidFileSizeException(Exception):
    pass

class MousePositionFile(StorageFile):
    def set_to_current_mouse_position(self):
        position = MousePosition.current()
        self.set(position)
    
    @classmethod
    def get_value_from_text(self, text: str):
        return MousePosition.from_text(text)
    
    def _initial_value(self):
        return MousePosition(0, 0)
    
class IntegerFile(StorageFile):
    @classmethod
    def get_value_from_text(self, text: str):
        return int(text)
    
    def _initial_value(self):
        return 0

class FloatFile(StorageFile):
    @classmethod
    def get_value_from_text(self, text: str):
        return float(text)
    
    def _initial_value(self):
        return 0.0
    
class StringFile(StorageFile):
    @classmethod
    def get_value_from_text(self, text: str):
        return text
    
    def _initial_value(self):
        return ''

class BooleanFile(StorageFile):
    @classmethod
    def get_value_from_text(self, text: str):
        return bool(text)
    
    def _initial_value(self):
        return False

    

    
