import os
import sys
from units import *
from cdb import *
import numpy

class CPU:
    def __init__(self, instructions: list[str]):
        """
        CPU

        Args:
            instructions: the list of instructions
        """
        self._instructions = instructions
        self._cdb = CommonDataBus()
        self._memory = MemoryUnit(self._cdb, 3, 3)
        self._register_file = FPRegisterFile(32, self._cdb)
        self._adder = FloatingPointUnit("Add", self._cdb, 3, {"ADDD": 2, "SUBD": 2})
        self._multiplier = FloatingPointUnit(
            "Mul", self._cdb, 2, {"MULTD": 10, "DIVD": 20}
        )
        self._pc = 0

    def issue(self, instruction: str) -> bool:
        """Issue an instruction

        Args:
            instruction: the instruction to issue
        Returns:
            True if the instruction is issued successfully, False otherwise
        Raises:
            ValueError: if the operation is invalid
        """
        op, dst, src1, src2 = instruction.split(" ")
        if op == "ADDD" or op == "SUBD":
            op1, op1_fu = self._register_file.read(int(src1[1:]))
            op2, op2_fu = self._register_file.read(int(src2[1:]))
            tag = self._adder.issue(op, op1, op1_fu, op2, op2_fu)
            self._register_file.set_fu(int(dst[1:]), tag)
        elif op == "MULTD" or op == "DIVD":
            op1, op1_fu = self._register_file.read(int(src1[1:]))
            op2, op2_fu = self._register_file.read(int(src2[1:]))
            tag = self._multiplier.issue(op, op1, op1_fu, op2, op2_fu)
            self._register_file.set_fu(int(dst[1:]), tag)
        elif op == "LD":
            tag = self._memory.issue_load(src2, "", src1.replace("+", ""))
            self._register_file.set_fu(int(dst[1:]), tag)
        elif op == "SD":
            data, data_fu = self._register_file.read(int(dst[1:]))
            tag = self._memory.issue_store(
                src2, "", src1.replace("+", ""), data, data_fu
            )
        else:
            raise ValueError(f"Invalid operation: {op}")
        return True if tag else False

    def run(self):
        """Run the CPU"""
        cycles = 1
        while (
            self._pc < len(self._instructions)
            or not self._adder.finished()
            or not self._multiplier.finished()
            or not self._memory.finished()
        ):
            print(f"Cycle_{cycles};")

            # Issue
            if self._pc < len(self._instructions):
                if self.issue(self._instructions[self._pc]):
                    self._pc += 1

            # Execute
            self._adder.tick()
            self._multiplier.tick()
            self._memory.tick()

            # Write back
            self._register_file.tick()
            self._cdb.tick()

            # Print
            for i, rs in enumerate(self._memory._load_buffers, 1):
                print(f"Load{i}:{'Yes' if rs['busy'] else 'No'},{rs['address']};")
            for i, rs in enumerate(self._memory._store_buffers, 1):
                print(f"Store{i}:{'Yes' if rs['busy'] else 'No'},{rs['address']},{rs['data_fu']};")
            for i, rs in enumerate(self._adder._rs, 1):
                print(f"Add{i}:{'Yes' if rs['busy'] else 'No'},{rs['op']},{rs['Vj']},{rs['Vk']},{rs['Qj']},{rs['Qk']};")
            for i, rs in enumerate(self._multiplier._rs, 1):
                print(f"Mult{i}:{'Yes' if rs['busy'] else 'No'},{rs['op']},{rs['Vj']},{rs['Vk']},{rs['Qj']},{rs['Qk']};")
            for i, rs in enumerate(self._register_file._registers):
                print(f"F{i}:{rs['fu']};", end="")
            print()

            cycles += 1



if __name__ == "__main__":
    os.makedirs("../output", exist_ok=True)

    with open("../input/input1.txt", "r") as f_in, open("../output/output1.txt", "w") as f_out:
        input1 = f_in.read().splitlines()
        # sys.stdout = f_out
        CPU(input1).run()

    with open("../input/input2.txt", "r") as f_in, open("../output/output2.txt", "w") as f_out:
        input2 = f_in.read().splitlines()
        sys.stdout = f_out
        CPU(input2).run()
