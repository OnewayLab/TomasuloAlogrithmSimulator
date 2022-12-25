from typing import Union
from cdb import CommonDataBus


class MemoryUnit:
    def __init__(self, cdb: CommonDataBus, n_buffers: int, n_cycles: int):
        """
        Memory Unit

        Args:
            cdb: the common data bus
            n_buffers: the number of buffers
            n_cycles: the number of cycles to load/store data
        """
        self.__cdb = cdb
        self.__n_buffers = n_buffers
        self.__n_cycles = n_cycles
        self.__memory: dict[int, int] = {}
        self.__load_buffers = [{"busy": False, "address": 0}] * n_buffers
        self.__load_buffer_head = 0
        self.__load_buffer_tail = 0
        self.__load_cycle_counter = 0
        self.__store_buffers = [
            {"busy": False, "address": 0, "data": 0.0, "fu": ""}
        ] * n_buffers
        self.__store_buffer_head = 0
        self.__store_buffer_tail = 0

    def issue_load(self, address: int) -> bool:
        """Issue a load instruction

        Args:
            address: the address to load data from

        Returns:
            True if successfully put the address into the load buffer, False otherwise
        """
        # Check if the load buffer is full
        if self.__load_buffers[self.__load_buffer_tail]["busy"]:
            return False

        # Put the address into the load buffer
        self.__load_buffers[self.__load_buffer_tail]["busy"] = True
        self.__load_buffers[self.__load_buffer_tail]["address"] = address
        self.__load_buffer_tail = (self.__load_buffer_tail + 1) % self.__n_buffers
        return True

    def issue_store(self, address: int, operand: Union[int, float, str]) -> bool:
        """Issue a store instruction

        Args:
            address: the address to store data to
            operand: the data to store or the reservation station that will produce it

        Returns:
            True if successfully put the address and data into the store buffer, False otherwise
        """
        # Check if the store buffer is full
        if self.__store_buffers[self.__store_buffer_tail]["busy"]:
            return False

        # Put the address and data into the store buffer
        self.__store_buffers[self.__store_buffer_tail] = {
            "busy": True,
            "address": address,
            "data": 0.0 if isinstance(operand, str) else operand,
            "fu": operand if isinstance(operand, str) else "",
        }
        self.__store_buffer_tail = (self.__store_buffer_tail + 1) % self.__n_buffers
        return True

    def execute(self):
        """Execute stage"""
        # Check if the load buffer is not empty
        if self.__load_buffers[self.__load_buffer_head]["busy"]:
            # Check if the load cycle counter is 0
            if self.__load_cycle_counter == 0:
                # Load data from memory
                address = self.__load_buffers[self.__load_buffer_head]["address"]
                data = self.__memory.get(address, 0)
                # Write data to CDB
                self.__cdb.write(f"Load{self.__load_buffer_head}", data)
                self.__load_buffer_head = (
                    self.__load_buffer_head + 1
                ) % self.__n_buffers
                # Set the load cycle counter
                self.__load_cycle_counter = self.__n_cycles
            else:
                # Update the load cycle counter
                self.__load_cycle_counter -= 1

        # Check CDB for required data
        tag, data = self.__cdb.read()
        if tag != "":
            for i in range(self.__n_buffers):
                if (
                    self.__store_buffers[i]["busy"]
                    and self.__store_buffers[i]["fu"] == tag
                ):
                    self.__store_buffers[i]["data"] = data
                    self.__store_buffers[i]["fu"] = ""

        # Check if the store buffer is not empty
        if (
            self.__store_buffers[self.__store_buffer_head]["busy"]
            and self.__store_buffers[self.__store_buffer_head]["fu"] == ""
        ):
            # Store data to memory
            address = self.__store_buffers[self.__store_buffer_head]["address"]
            data = self.__store_buffers[self.__store_buffer_head]["data"]
            self.__memory[address] = data
            # Write data to CDB
            self.__cdb.write(f"Store{self.__store_buffer_head}", data)
            self.__store_buffer_head = (self.__store_buffer_head + 1) % self.__n_buffers

    def write_back(self):
        """Write-back stage"""
        # Check CDB for required data
        tag, data = self.__cdb.read()
        if tag != "":
            for i in range(self.__n_buffers):
                if (
                    self.__load_buffers[i]["busy"]
                    and self.__load_buffers[i]["fu"] == tag
                ):
                    self.__load_buffers[i]["fu"] = ""

class FloatingPointUnit:
    def __init__(self, name: str, cdb: CommonDataBus, n_rs: int, n_cycles: dict[str, int]):
        """
        Floating-point Functional Unit, can be FPAdder or FPMultiplier

        Args:
            name: the name of the functional unit, either "Add" or "Mul"
            cdb: the common data bus
            n_rs: the number of reservation stations
            n_cycles: the number of cycles to execute an operation, in the form of {"Op": n}
        """
        self.__name = name
        self.__cdb = cdb
        self.__n_rs = n_rs
        self.__n_cycles = n_cycles
        self.__rs = [
            {"busy": False, "op": "", "Vj": 0.0, "Vk": 0.0, "Qj": "", "Qk": ""}
        ] * n_rs
        self.__rs_head = 0
        self.__rs_tail = 0
        self.__cycle_counter = -1   # -1 means no operation is being executed

    def issue(self, op: str, op1: Union[float, str], op2: Union[float, str]) -> bool:
        """Issue an operation

        Args:
            op: the operation, can be "ADDD", "SUBD", "MULD" or "DIVD"
            op1: the first operand or the reservation station that will produce it
            op2: the second operand or the reservation station that will produce it

        Returns:
            True if successfully put the operation into the reservation station, False otherwise
        """
        # Check if the reservation station is full
        if self.__rs[self.__rs_tail]["busy"]:
            return False

        # Put the operation into the reservation station
        self.__rs[self.__rs_tail] = {
            "busy": True,
            "op": op,
            "Vj": 0.0 if isinstance(op1, str) else op1,
            "Qj": op1 if isinstance(op1, str) else "",
            "Vk": 0.0 if isinstance(op2, str) else op2,
            "Qk": op2 if isinstance(op2, str) else "",
        }
        self.__rs_tail = (self.__rs_tail + 1) % self.__n_rs
        return True

    def tick(self):
        """Tick the clock"""
        # Check CDB for required data
        tag, data = self.__cdb.read()
        if tag != "":
            for i in range(self.__n_rs):
                if self.__rs[i]["busy"]:
                    if self.__rs[i]["Qj"] == tag:
                        self.__rs[i]["Vj"] = data
                        self.__rs[i]["Qj"] = ""
                    if self.__rs[i]["Qk"] == tag:
                        self.__rs[i]["Vk"] = data
                        self.__rs[i]["Qk"] = ""

        # Check if the reservation station is not empty
        if self.__rs[self.__rs_head]["busy"]:
            if self.__cycle_counter == -1:
                # Check if the operation is ready to execute
                if self.__rs[self.__rs_head]["Qj"] == "" and self.__rs[self.__rs_head]["Qk"] == "":
                    # Set the cycle counter
                    self.__cycle_counter = self.__n_cycles[self.__rs[self.__rs_head]["op"]]
            else:
                # Update the cycle counter
                self.__cycle_counter -= 1
                # Check if the operation is finished
                if self.__cycle_counter == 0:
                    # Execute the operation
                    op = self.__rs[self.__rs_head]["op"]
                    op1 = self.__rs[self.__rs_head]["Vj"]
                    op2 = self.__rs[self.__rs_head]["Vk"]
                    if op == "ADDD":
                        result = op1 + op2
                    elif op == "SUBD":
                        result = op1 - op2
                    elif op == "MULD":
                        result = op1 * op2
                    elif op == "DIVD":
                        result = op1 / op2
                    # Write data to CDB
                    self.__cdb.write(f"{self.__name}{self.__rs_head}", result)
                    self.__rs_head = (self.__rs_head + 1) % self.__n_rs
                    # Reset the cycle counter
                    self.__cycle_counter = -1


class FPRegisterFile:
    def __init__(self, n_registers: int, cbd: CommonDataBus):
        """
        Floating-point Register File

        Args:
            n_registers: the number of registers
            cbd: the common data bus
        """
        self.__n_registers = n_registers
        self.__cbd = cbd
        self.__registers = [{"fu": "", "data": 0.0}] * n_registers

    def read(self, register: int) -> Union[float, str]:
        """Read a register

        Args:
            register: the register to read

        Returns:
            the value of the register or the functional unit that will produce it
        """
        tag, data = self.__cbd.read()
        if tag == self.__registers[register]["fu"]:
            return data
        elif self.__registers[register]["fu"] == "":
            return self.__registers[register]["data"]
        else:
            return self.__registers[register]["fu"]

    def tick(self):
        """Tick the clock"""
        # Check CDB for required data
        tag, data = self.__cbd.read()
        if tag != "":
            for i in range(self.__n_registers):
                if self.__registers[i]["fu"] == tag:
                    self.__registers[i]["data"] = data
                    self.__registers[i]["fu"] = ""