#!/usr/bin/env python

from distutils.core import setup

setup(name='session_ui',
      version='0.1',
      description='Simple Python based UI for ConnMan Session API',
      author='Daniel Wagner',
      author_email='daniel.wagner@bmw-carit.de',
      url='http://git.bmw-carit.de/?p=session-ui.git;a=summary',
      packages=['session_ui'],
      package_dir={'session_ui': 'src'},
      package_data={'session_ui': ['ui/*.ui']},
      data_files=[('share/applications', ['session-ui.desktop'])],
      license='GPLv2',
      options={'bdist_rpm': {'requires': 'PyQt4',
                             'group':    'User Interface/Desktops',
                             'vendor':   'The Session UI Team'}},
      scripts=['session-ui']
     )
