from datetime import date, datetime


# Error with VCC problems
class VCCError(Exception):
    def __init__(self, err_msg):
        self.err_msg = err_msg


# Change dictionary to attribute of a class
def make_object(data, cls=None):
    # Change a iso format string to datetime. Return string if not datetime
    def decode_obj(val):
        try:
            return datetime.fromisoformat(val)
        except (ValueError, TypeError):
            return val

    # Use empty Obj class if one is not provided
    cls = cls if cls else type('Obj', (), {})()

    # Set attribute of the class
    for key, value in data.items():
        if isinstance(value, dict):
            setattr(cls, key, make_object(value))
        elif isinstance(value, list):
            setattr(cls, key, [decode_obj(val) for val in value])
        else:
            setattr(cls, key, decode_obj(value))
    return cls


# Encode date and datetime object in special dict object
def json_encoder(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {name: json_encoder(item) for name, item in obj.items()}
    if isinstance(obj, list):
        return [json_encoder(item) for item in obj]
    return obj


# Decode date and datetime object in string with isoformat
def json_decoder(obj):
    try:
        return datetime.fromisoformat(obj)
    except:
        if isinstance(obj, dict):
            return {name: json_decoder(item) for name, item in obj.items()}
        if isinstance(obj, list):
            return [json_decoder(item) for item in obj]
    return obj
