# -*- coding: utf-8 -*-


class VersionInfo:
    """
        This class holds the version information of sapns server.
    """
    def __init__(self, product_name, major_version, minor_version, build_version, os_platform, current_date, current_time, product_flavour, device_and_ip_count):
        self.product_name = product_name
        self.major_version = major_version
        self.minor_version = minor_version
        self.build_version = build_version
        self.os_platform = os_platform
        self.current_date = current_date
        self.current_time = current_time
        self.product_flavour = product_flavour
        self.device_and_ip_count = device_and_ip_count
