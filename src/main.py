import os
import sys
from units import *
from cdb import *


class CPU:
    def __init__(self, instructions: list[str]):
        """
        CPU

        Args:
            instructions: the list of instructions
        """
        self.__instructions = instructions
        self.__cdb = CommonDataBus()
        self.__memory = MemoryUnit(self.__cdb, 3, 3)
        self.__register_file = FPRegisterFile(32, self.__cdb)
        self.__adder = FloatingPointUnit("Add", self.__cdb, 3, {"ADDD": 2, "SUBD": 2})
        self.__multiplier = FloatingPointUnit(
            "Mul", self.__cdb, 2, {"MULD": 10, "DIVD": 20}
        )
        self.__pc = 0

    def issue(self, instruction: str) -> bool:
        """Issue an instruction

        Args:
            instruction: the instruction to issue
        Returns:
            True if the instruction is issued successfully, False otherwise
        """
        op, dst, src1, src2 = instruction.split(" ")
        if op == "ADDD" or op == "SUBD":
            op1, op1_fu = self.__register_file.read(int(src1[1:]))
            op2, op2_fu = self.__register_file.read(int(src2[1:]))
            tag = self.__adder.issue(op, op1, op1_fu, op2, op2_fu)
            self.__register_file.set_fu(int(dst[1:]), tag)
        elif op == "MULD" or op == "DIVD":
            op1, op1_fu = self.__register_file.read(int(src1[1:]))
            op2, op2_fu = self.__register_file.read(int(src2[1:]))
            tag = self.__multiplier.issue(op, op1, op1_fu, op2, op2_fu)
            self.__register_file.set_fu(int(dst[1:]), tag)
        elif op == "LD":
            tag = self.__memory.issue_load(src2, "", src1.replace("+", ""))
            self.__register_file.set_fu(int(dst[1:]), tag)
        elif op == "SD":
            data, data_fu = self.__register_file.read(int(dst[1:]))
            tag = self.__memory.issue_store(
                src2, "", src1.replace("+", ""), data, data_fu
            )
        return True if tag else False

    def run(self):
        """Run the CPU"""
        while (
            self.__pc < len(self.__instructions)
            or not self.__adder.finished()
            or not self.__multiplier.finished()
            or not self.__memory.finished()
        ):
            # Issue
            if self.__pc < len(self.__instructions):
                if self.issue(self.__instructions[self.__pc]):
                    self.__pc += 1

            # Execute
            self.__adder.tick()
            self.__multiplier.tick()
            self.__memory.tick()

            # Write back
            self.__register_file.tick()
            self.__cdb.tick()

        # Print the result
        print(self.__register_file)


if __name__ == "__main__":
    os.makedirs("../output", exist_ok=True)

    with open("../input/input1.txt", "r") as f_in, open("../output/output1.txt", "w") as f_out:
        input1 = f_in.read().splitlines()
        sys.stdout = f_out
        CPU(input1).run()

    with open("../input/input2.txt", "r") as f_in, open("../output/output2.txt", "w") as f_out:
        input2 = f_in.read().splitlines()
        sys.stdout = f_out
        CPU(input2).run()
