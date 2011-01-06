"""
This is the fll.config module, it provides a class for abstracting the
fll configuration file and command line arguments.

Authour:   Kel Modderman
Copyright: Copyright (C) 2010 Kel Modderman <kel@otaku42.de>
License:   GPL-2
"""

from configobj import ConfigObj, ConfigObjError, \
                      flatten_errors, get_extra_values
from validate import Validator
import fll.misc
import os
import sys


class ConfigError(Exception):
    """
    An Error class for use by Config.
    """
    pass


class Config(object):
    """
    A class for abstracting the fll configuration file.

    Options       Type        Description
    --------------------------------------------------------------------------
    config_file - (str)       pathname to config file
    cmdline     - (Namespace) an argparse Namespace object
    """
    def __init__(self, config_file=None, cmdline=None):
        if config_file is None:
            if os.path.isfile('conf/fll.conf'):
                self.config_file = os.path.realpath('conf/fll.conf')
            else:
                self.config_file = os.path.realpath('/etc/fll/fll.conf')
        elif isinstance(config_file, file):
            self.config_file = os.path.realpath(config_file.name)
        elif os.path.isfile(config_file):
            self.config_file = os.path.realpath(config_file)
        else:
            raise ConfigError('%s does not exist' % config_file)

        if os.path.isfile('conf/fll.conf.spec'):
            self.config_spec = os.path.realpath('conf/fll.conf.spec')
        else:
            self.config_spec = '/usr/share/fll/fll.conf.spec'

        self.config = ConfigObj(self.config_file,
                                configspec=self.config_spec,
                                interpolation='template')

        self._process_cmdline(cmdline)
        self._validate()
        self._propogate_modes()

        if self.config['verbosity'] == 'debug':
            import pprint
            pprint.pprint(dict(self.config))

    def _validate(self):
        result = self.config.validate(Validator(), preserve_errors=True)
        error_msgs = []

        for sections, name in get_extra_values(self.config):
            the_section = self.config
            try:
                for section in sections:
                    the_section = self.config[section]
            except KeyError:
                continue

            the_value = the_section[name]

            section_or_value = 'value'
            if isinstance(the_value, dict):
                section_or_value = 'section'

            section_string = ', '.join(sections) or 'top level'

            msg = 'E: extra %s entry in %s section: %r' % \
                  (section_or_value, section_string, name)
            error_msgs.append(msg)

        for entry in flatten_errors(self.config, result):
            section_list, key, error = entry
            if key is None:
                section_list.append('section missing')
            else:
                section_list.append(key)

            if error == False:
                error = 'value or section missing'

            msg = 'E: config%s: %s' % \
                  (''.join(["['%s']" % s for s in section_list]), error)
            error_msgs.append(msg)

        if error_msgs:
            error_msgs.insert(0, 'config file failed validation: %s' %
                              self.config_file)
            raise ConfigError('\n'.join(error_msgs))

    def _process_cmdline(self, args):
        if args is None:
            return

        if args.architecture:
            self.config['architecture'] = args.architecture
        elif 'architecture' not in self.config:
            arch = fll.misc.cmd('dpkg --print-architecture', pipe=True,
                                silent=True)
            self.config['architecture'] = [arch.strip()]

        if args.build_dir:
            self.config['build_dir'] = args.build_dir
        elif 'build_dir' not in self.config:
            self.config['build_dir'] = os.getcwd()

        if args.dryrun:
            self.config['dryrun'] = args.dryrun

        if args.ftp_proxy:
            self.config['ftp_proxy'] = args.ftp_proxy

        if args.http_proxy:
            self.config['http_proxy'] = args.http_proxy

        if args.mirror:
            self.config['mirror'] = args.mirror

        if args.preserve_chroot:
            self.config['chroot']['preserve'] = args.preserve_chroot

        if args.insecure:
            self.config['apt']['secure'] = False

        if args.source:
            self.config['apt']['fetch_src'] = args.source

        if args.verbosity:
            self.config['verbosity'] = args.verbosity
        elif args.quiet:
            self.config['verbosity'] = 'quiet'
        elif args.verbose:
            self.config['verbosity'] = 'verbose'
        elif args.debug:
            self.config['verbosity'] = 'debug'

    def _propogate_modes(self):
        sections = ['apt', 'chroot']
        mode = self.config['verbosity']

        for section in sections:
            self.config[section][mode] = True

    def set_environment(self):
        for k, v in self.config['environment'].iteritems():
            os.putenv(k, v)
        for k in os.environ.iterkeys():
            if k in self.config['environment']:
                continue
            os.unsetenv(k)
        os.environ = self.config['environment']

        if self.config['http_proxy']:
            os.putenv('http_proxy', self.config['http_proxy'])
            os.environ['http_proxy'] = \
                self.config['apt']['conf']['Acquire::http::Proxy'] = \
                self.config['http_proxy']

        if self.config['ftp_proxy']:
            os.putenv('ftp_proxy', self.config['ftp_proxy'])
            os.environ['ftp_proxy'] = \
                self.config['apt']['conf']['Acquire::ftp::Proxy'] = \
                self.config['ftp_proxy']
