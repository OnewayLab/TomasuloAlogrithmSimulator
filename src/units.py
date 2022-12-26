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
        self._registers = [{"fu": "", "data": f"R(F{i})"} for i in range(n_registers)]

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
            return self._registers[register]["data"], ""
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
        if tag != "":
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
        self._memory: dict[int, str] = {}
        self._load_buffers = [{"busy": False, "address": ""}] * n_buffers
        self._load_buffer_head = 0
        self._load_buffer_tail = 0
        self._load_cycle_counter = -1
        self._store_buffers = [
            {"busy": False, "address": "", "data": "", "fu": ""}
        ] * n_buffers
        self._store_buffer_head = 0
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
            "data": data,
            "fu": fu,
        }
        tag = f"Store{self._store_buffer_tail+1}"
        self._store_buffer_tail = (self._store_buffer_tail + 1) % self._n_buffers
        return tag

    def tick(self):
        """Tick the clock"""
        # Check CDB for required data
        tag, data = self._cdb.read()
        if tag:
            for i in range(self._n_buffers):
                if self._store_buffers[i]["busy"] and self._store_buffers[i]["fu"] == tag:
                    self._store_buffers[i]["data"] = data
                    self._store_buffers[i]["fu"] = ""

        # Check if the load buffer is not empty
        if self._load_buffers[self._load_buffer_head]["busy"]:
            if self._load_cycle_counter == -1:
                # Set the cycle counter
                self._load_cycle_counter = self._n_cycles
            else:
                # Update the cycle counter
                self._load_cycle_counter -= 1
                # Check if the load operation is finished
                if self._load_cycle_counter == 1:   # Execution finished
                    # Load data from memory
                    address = self._load_buffers[self._load_buffer_head]["address"]
                    data = self._memory.get(address, f"M({address})")
                    # Write data to CDB
                    self._cdb.write(f"Load{self._load_buffer_head + 1}", data)
                elif self._load_cycle_counter == 0: # Write back finished
                    # Reset the reservation station and the cycle counter
                    self._load_buffers[self._load_buffer_head] = {
                        "busy": False,
                        "address": "",
                    }
                    self._load_buffer_head = (
                        self._load_buffer_head + 1
                    ) % self._n_buffers


        # Check if the store buffer is not empty and the base address and data are ready
        if (
            self._store_buffers[self._store_buffer_head]["busy"]
            and self._store_buffers[self._store_buffer_head]["fu"] == ""
        ):
            # Store data to memory
            address = self._store_buffers[self._store_buffer_head]["address"]
            data = self._store_buffers[self._store_buffer_head]["data"]
            self._memory[address] = data
            self._store_buffer_head = (self._store_buffer_head + 1) % self._n_buffers
            # Reset the reservation station
            self._store_buffers[self._store_buffer_head] = {
                "busy": False,
                "address": "",
                "data": "",
                "fu": "",
            }

    def finished(self):
        """Check if all the buffers are empty"""
        return (
            not self._load_buffers[self._load_buffer_head]["busy"]
            and not self._store_buffers[self._store_buffer_head]["busy"]
        )


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
            {"busy": False, "op": "", "Vj": "", "Vk": "", "Qj": "", "Qk": ""}
        ] * n_rs
        self._rs_head = 0
        self._rs_tail = 0
        self._cycle_counter = -1  # -1 means no operation is being executed

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
        }
        tag = f"{self._name}{self._rs_tail+1}"
        self._rs_tail = (self._rs_tail + 1) % self._n_rs
        return tag

    def tick(self):
        """Tick the clock"""
        # Check CDB for required data
        tag, data = self._cdb.read()
        if tag:
            for i in range(self._n_rs):
                if self._rs[i]["busy"]:
                    if self._rs[i]["Qj"] == tag:
                        self._rs[i]["Vj"] = data
                        self._rs[i]["Qj"] = ""
                    if self._rs[i]["Qk"] == tag:
                        self._rs[i]["Vk"] = data
                        self._rs[i]["Qk"] = ""

        # Check if the reservation station is not empty
        if self._rs[self._rs_head]["busy"]:
            if self._cycle_counter == -1:
                # Check if the operation is ready to execute
                if (
                    self._rs[self._rs_head]["Qj"] == ""
                    and self._rs[self._rs_head]["Qk"] == ""
                ):
                    # Set the cycle counter
                    self._cycle_counter = self._n_cycles[
                        self._rs[self._rs_head]["op"]
                    ]
            else:
                # Update the cycle counter
                self._cycle_counter -= 1
                # Check if the operation is finished
                if self._cycle_counter == 1:    # Execution finished
                    # Execute the operation
                    op = self._rs[self._rs_head]["op"]
                    op1 = self._rs[self._rs_head]["Vj"]
                    op2 = self._rs[self._rs_head]["Vk"]
                    if op == "ADDD":
                        result = f"{op1}+{op2}"
                    elif op == "SUBD":
                        result = f"{op1}-{op2}"
                    elif op == "MULTD":
                        result = f"{op1}*{op2}"
                    elif op == "DIVD":
                        result = f"{op1}/{op2}"
                    # Write data to CDB
                    self._cdb.write(f"{self._name}{self._rs_head + 1}", result)
                elif self._cycle_counter == 0:  # Write back finished
                    # Reset the reservation station and the cycle counter
                    self._rs[self._rs_head] = {
                        "busy": False,
                        "op": "",
                        "Vj": "",
                        "Vk": "",
                        "Qj": "",
                        "Qk": "",
                    }
                    self._rs_head = (self._rs_head + 1) % self._n_rs

    def finished(self):
        """Check if all the reservation stations are empty"""
        return not self._rs[self._rs_head]["busy"]