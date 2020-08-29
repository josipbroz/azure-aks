import logging
import toml

class ConfigToml:
    def __init__(self):
        self.logger = logging.getLogger('azlogger')

    def readConfig(self, configfile):
        self.configfile = configfile
        self.logger.info('Reading config file %s', configfile)
        try:
            configfile = toml.load(configfile)
        except IOError as e:
            return configfile, e
        else:
            return configfile, None

# def _validate_file():
# define lists of required parameters and make sure they are all 
# present. If any one is missing return an error