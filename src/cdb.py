class CommonDataBus:
    """
    Common Data Bus
    """
    def __init__(self):
        self.__data = None
        self.__tag = None

    def read(self):
        """Read data from CDB

        Returns:
            tag: the reservation station tag
            data: the data read from CDB
        """
        return self.__tag, self.__data

    def write(self, tag: str, data: float):
        """Write data to CDB

        Args:
            tag: the reservation station tag
            data: the data to write
        """
        self.__tag = tag
        self.__data = data
