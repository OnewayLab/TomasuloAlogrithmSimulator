import os
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
        self.__multiplier = FloatingPointUnit("Mul", self.__cdb, 2, {"MULD": 10, "DIVD": 20})
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
            operand1 = self.__register_file.read(src1)
            operand2 = self.__register_file.read(src2)
            return self.__adder.issue(op, operand1, operand2)
        elif op == "MULD" or op == "DIVD":
            return self.__multiplier.issue(op, dst, src1, src2)
        elif op == "LD" or op == "SD":
            return self.__memory.issue(op, dst, src1, src2)

    def run(self):
        """Run the CPU"""
        while self.__pc < len(self.__instructions):
            # Issue
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
    # Get the path of the input file
    with open("input1.txt", "r") as f:
        input1 = f.read().splitlines()

    cpu = CPU(input1)

    with open("input2.txt", "r") as f:
        input2 = f.read().splitlines()