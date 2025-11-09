

class SaproException(Exception):

    """
        This class is derived from 'Exception' class. This class holds the
        error message raised during application execution. It should be catched
        by calling application.
    """

    def __init__(self, errStr):
        """
            Constructs SaproException object with detailed error message
            from errStr.
        """
        Exception.__init__(self, errStr)
        if errStr is not None:
            self.strVal = "SAPRO Exception : %s" %errStr
        else:
            self.strVal = ""

    def toString(self):
        """
            Returns the error message.
        """
        return self.strVal