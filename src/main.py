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

    def tick(self):
        """Tick the clock"""
        self.__memory.tick()
        self.__register_file.tick()
        self.__adder.tick()
        self.__multiplier.tick()


if __name__ == "__main__":
    # Get the path of the input file
    with open("input1.txt", "r") as f:
        input1 = f.read().splitlines()

    cpu = CPU(input1)

    with open("input2.txt", "r") as f:
        input2 = f.read().splitlines()