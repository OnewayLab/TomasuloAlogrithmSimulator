from typing import Union
from cdb import CommonDataBus


class FPRegisterFile:
    def __init__(self, n_registers: int, cbd: CommonDataBus):
        """
        Floating-point Register File

        Args:
            n_registers: the number of registers
            cbd: the common data bus
        """
        self._n_registers = n_registers
        self._cbd = cbd
        self._registers = [{"fu": "", "data": ""} for i in range(n_registers)]

    def read(self, register: int) -> tuple[str, str]:
        """Read a register

        Args:
            register: the register to read

        Returns:
            if the register is ready, return the data in the register and "",
            otherwise, return "" and the tag of the functional unit that is writing to the register
        """
        tag, data = self._cbd.read()
        if tag and tag == self._registers[register]["fu"]:
            return data, ""
        elif self._registers[register]["fu"] == "":
            return self._registers[register]["data"] if self._registers[register]["data"] else f"R(F{register})", ""
        else:
            return "", self._registers[register]["fu"]

    def set_fu(self, register: int, fu: str):
        """Set the functional unit that is writing to the register

        Args:
            register: the register to write
            fu: the tag of the functional unit
        """
        self._registers[register]["fu"] = fu

    def tick(self):
        """Tick the clock"""
        # Check CDB for required data
        tag, data = self._cbd.read()
        if tag:
            for i in range(self._n_registers):
                if self._registers[i]["fu"] == tag:
                    self._registers[i]["data"] = data
                    self._registers[i]["fu"] = ""


class MemoryUnit:
    def __init__(self, cdb: CommonDataBus, n_buffers: int, n_cycles: int):
        """
        Memory Unit

        Args:
            cdb: the common data bus
            n_buffers: the number of buffers
            n_cycles: the number of cycles to load/store data
        """
        self._cdb = cdb
        self._n_buffers = n_buffers
        self._n_cycles = n_cycles
        self._memory: dict[str, str] = {}
        self._load_buffers = [{"busy": False, "address": "", "counter": -1}] * n_buffers
        self._load_buffer_tail = 0
        self._store_buffers = [
            {"busy": False, "address": "", "fu": "", "counter": -1}
        ] * n_buffers
        self._store_buffer_tail = 0

    def issue_load(self, base: str, offset: str) -> str:
        """Issue a load instruction

        Args:
            base: the base address
            offset: the offset

        Returns:
            The reservation station if successfully put the address into the load buffer, "" otherwise
        """
        # Check if the load buffer is full
        if self._load_buffers[self._load_buffer_tail]["busy"]:
            return ""

        # Put the address into the load buffer
        self._load_buffers[self._load_buffer_tail] = {
            "busy": True,
            "address": f"{offset}+{base}",
            "counter": self._n_cycles + 1,
        }
        tag = f"Load{self._load_buffer_tail+1}"
        self._load_buffer_tail = (self._load_buffer_tail + 1) % self._n_buffers
        return tag

    def issue_store(
        self, base: str, offset: str, data: str, fu: str
    ) -> str:
        """Issue a store instruction

        Args:
            base: the base address
            offset: the offset
            data: the data to store if it's ready, "" otherwise
            fu: the tag of the functional unit that will produce the data

        Returns:
            The reservation station tag if successful, "" otherwise
        """
        # Check if the store buffer is full
        if self._store_buffers[self._store_buffer_tail]["busy"]:
            return ""

        # Put the address and data into the store buffer
        self._store_buffers[self._store_buffer_tail] = {
            "busy": True,
            "address": f"{offset}+{base}" if base else offset,
            "fu": fu if fu else data,
            "counter": -1 if fu else (self._n_cycles + 1),
        }
        tag = f"Store{self._store_buffer_tail+1}"
        self._store_buffer_tail = (self._store_buffer_tail + 1) % self._n_buffers
        return tag

    def tick(self):
        """Tick the clock"""
        # Read data from CDB
        tag, data = self._cdb.read()

        # Check each load buffer
        for i, buffer in enumerate(self._load_buffers):
            if buffer["busy"]:
                if buffer["counter"] == 1:  # Execution finished
                    result = self._memory.get(buffer["address"], f"M({buffer['address']})")
                    self._cdb.write(f"Load{i+1}", result)
                    buffer["counter"] -= 1
                elif buffer["counter"] == 0:    # Write back finished
                    buffer["busy"] = False
                    buffer["address"] = ""
                else:   # Executing
                    buffer["counter"] -= 1

        # Check each store buffer
        for buffer in self._store_buffers:
            if buffer["busy"]:
                if buffer["counter"] == -1: # Data is not ready
                    if tag and tag == buffer["fu"]:
                        buffer["fu"] = data
                        buffer["counter"] = self._n_cycles
                elif buffer["counter"] == 1:    # Execution finished
                    self._memory[buffer["address"]] = buffer["fu"]
                    buffer["counter"] -= 1
                elif buffer["counter"] == 0:    # Write back finished
                    buffer["busy"] = False
                    buffer["address"] = ""
                    buffer["fu"] = ""
                else:   # Executing
                    buffer["counter"] -= 1

    def finished(self):
        """Check if all the buffers are empty"""
        for buffer in self._load_buffers:
            if buffer["busy"]:
                return False
        for buffer in self._store_buffers:
            if buffer["busy"]:
                return False
        return True


class FloatingPointUnit:
    def __init__(
        self, name: str, cdb: CommonDataBus, n_rs: int, n_cycles: dict[str, int]
    ):
        """
        Floating-point Functional Unit, can be FPAdder or FPMultiplier

        Args:
            name: the name of the functional unit, either "Add" or "Mul"
            cdb: the common data bus
            n_rs: the number of reservation stations
            n_cycles: the number of cycles to execute an operation, in the form of {"Op": n}
        """
        self._name = name
        self._cdb = cdb
        self._n_rs = n_rs
        self._n_cycles = n_cycles
        self._rs = [
            {"busy": False, "op": "", "Vj": "", "Vk": "", "Qj": "", "Qk": "", "counter": -1}
        ] * n_rs
        self._rs_tail = 0

    def issue(self, op: str, op1: str, op1_fu:str, op2: str, op2_fu: str) -> str:
        """Issue an operation

        Args:
            op: the operation, can be "ADDD", "SUBD", "MULD" or "DIVD"
            op1: the first operand if it's ready, otherwise ""
            op1_fu: the functional unit that will produce the first operand
            op2: the second operand if it's ready, otherwise ""
            op2_fu: the functional unit that will produce the second operand

        Returns:
            The reservation station tag if the operation is successfully issued, otherwise ""
        """
        # Check if the reservation station is full
        if self._rs[self._rs_tail]["busy"]:
            return ""

        # Put the operation into the reservation station
        self._rs[self._rs_tail] = {
            "busy": True,
            "op": op,
            "Vj": op1,
            "Qj": op1_fu,
            "Vk": op2,
            "Qk": op2_fu,
            "counter": (self._n_cycles[op] + 1) if op1 and op2 else -1,
        }
        tag = f"{self._name}{self._rs_tail+1}"
        self._rs_tail = (self._rs_tail + 1) % self._n_rs
        return tag

    def tick(self):
        """Tick the clock"""
        # Check CDB for required data
        tag, data = self._cdb.read()

        # Check each reservation station
        for i, rs in enumerate(self._rs):
            if rs["busy"]:
                if rs["counter"] == -1: # Data is not ready
                    if tag and tag == rs["Qj"]:
                        rs["Vj"] = data
                        rs["Qj"] = ""
                    if tag and tag == rs["Qk"]:
                        rs["Vk"] = data
                        rs["Qk"] = ""
                    if rs["Vj"] and rs["Vk"]:
                        rs["counter"] = self._n_cycles[rs["op"]]
                elif rs["counter"] == 1:    # Execution finished
                    if rs["op"] == "ADDD":
                        result = f"{rs['Vj']}+{rs['Vk']}"
                    elif rs["op"] == "SUBD":
                        result = f"{rs['Vj']}-{rs['Vk']}"
                    elif rs["op"] == "MULTD":
                        result = f"{rs['Vj']}*{rs['Vk']}"
                    elif rs["op"] == "DIVD":
                        result = f"{rs['Vj']}/{rs['Vk']}"
                    else:
                        raise ValueError(f"Unknown operation {rs['op']}")
                    self._cdb.write(f"{self._name}{i+1}", result)
                    rs["counter"] -= 1
                elif rs["counter"] == 0:    # Write back finished
                    rs["busy"] = False
                    rs["op"], rs["Vj"], rs["Vk"], rs["Qj"], rs["Qk"] = "", "", "", "", ""
                else:   # Executing
                    rs["counter"] -= 1

    def finished(self):
        """Check if all the reservation stations are empty"""
        for rs in self._rs:
            if rs["busy"]:
                return False
        return True