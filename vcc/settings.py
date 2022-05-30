import sys

import toml

from vcc import make_object


# Flag configuration problems
class BadConfigurationFile(Exception):
    def __init__(self, err_msg):
        self.err_msg = err_msg


# Get application input options and parameters
def init(args):
    # Initialize global variables
    this_module = sys.modules[__name__]

    # Store all arguments under args variable
    setattr(this_module, 'args', args)
    if hasattr(args, 'config'):
        try:
            data = toml.load(open(args.config))
        except toml.TomlDecodeError as exc:
            raise BadConfigurationFile(f'Error reading {args.config} [{str(exc)}]')
        # Add information in config file to this module
        make_object(data, this_module)

    return args


def check_privilege(group_id):
    this_module = sys.modules[__name__]
    return hasattr(this_module.Signatures, group_id)

