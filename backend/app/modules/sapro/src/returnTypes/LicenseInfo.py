# -*- coding: utf-8 -*-
from collections import namedtuple
"""
    'licenseInfo' is a tuple that holds minimal license
    information of sapns server.
"""
licenseInfo = namedtuple('licenseInfo', ['maxDeviceCount', 'currentDeviceCount', 'licenseType', 'errorCode'])
fullLicenseInfo = namedtuple('fullLicenseInfo', ['maxDeviceCount', 'currentDeviceCount', 'licenseType',
                                                 'expiryDate', 'registrationId', 'hostId', 'moduleMask',
                                                 'errorCode', 'licenseServerIp', 'licenseServerPort'])