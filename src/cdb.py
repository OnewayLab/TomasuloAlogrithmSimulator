class CommonDataBus:
    """
    Common Data Bus
    """
    def __init__(self):
        self._tag = ""
        self._data = ""
        self._new_tag = ""
        self._new_data = ""

    def read(self) -> tuple[str, str]:
        """Read data from CDB

        Returns:
            tag: the reservation station tag
            data: the data read from CDB
        """
        return self._tag, self._data

    def write(self, tag: str, data: str):
        """Write data to CDB

        Args:
            tag: the reservation station tag
            data: the data to write
        """
        self._new_tag = tag
        self._new_data = data

    def tick(self):
        """Tick the clock"""
        self._tag, self._data = self._new_tag, self._new_data
        self._new_tag, self._new_data = "", ""

