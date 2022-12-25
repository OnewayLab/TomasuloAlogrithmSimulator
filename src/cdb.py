class CommonDataBus:
    """
    Common Data Bus
    """
    def __init__(self):
        self.__tag = ""
        self.__data = ""
        self.__new_tag = ""
        self.__new_data = ""

    def read(self) -> tuple[str, str]:
        """Read data from CDB

        Returns:
            tag: the reservation station tag
            data: the data read from CDB
        """
        return self.__tag, self.__data

    def write(self, tag: str, data: str):
        """Write data to CDB

        Args:
            tag: the reservation station tag
            data: the data to write
        """
        self.__new_tag = tag
        self.__new_data = data

    def tick(self):
        """Tick the clock"""
        self.__tag = self.__new_tag
        self.__data = self.__new_data
