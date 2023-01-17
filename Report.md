# Tomasulo 算法实验报告

## 项目结构

```
HW5
├─ input                // 输入样例
│  ├─ input1.txt
│  └─ input2.txt
├─ output               // 输出结果
│  ├─ output1.txt
│  └─ output2.txt
└─ src                  // 源代码
   ├─ cdb.py            // 公共数据总线
   ├─ main.py           // 主程序
   └─ units.py          // 功能单元
```

运行程序前请确保项目结构如上所示，运行方式：

```bash
cd src
python main.py
```

## 假设

针对作业要求中未说明的细节，我在本次实验中采用以下假设，绝大部分假设与课件“Chap03-ILP-Part3-TomasuloExample”一致。

1. Store 指令执行所需周期数与 Load 指令相同，为 2 个时钟周期。
2. 同一功能单元不同保留站中的指令可以同时执行。
3. 需要考虑的指令仅包含两个输入样例中出现的指令。
4. 由于不知道寄存器和内存中的初始值，首次从整数寄存器中读出的值用 `R?` 表示，首次从浮点寄存器中读出的值用 `R(F?)` 表示，其中 `?` 为寄存器编号；首次从内存中读出的值用 `M(?)` 表示，其中 `?` 为内存地址。（这里没有直接假设初始值为 0，既是为了与课件保持一致，也是为了防止在 `DIVD` 指令处出现除零错误。）

## 关键代码展示

源代码中有详细的英文注释，为了防止报告过长，下面贴出的代码略去了部分注释，旨在快速阐明整个项目的架构和原理。

### `CPU` 类

`CPU` 类位于 `main.py` 中，负责连接各个功能单元、执行程序和打印输出。

```python
class CPU:
    def __init__(self, instructions: list[str]):
        self._instructions = instructions
        self._issue_cycle = [0] * len(instructions) # A record of when each instruction is issued
        self._finish_cycle = [0] * len(instructions) # A record of when each instruction is finished
        self._cdb = CommonDataBus()
        self._memory = MemoryUnit(self._cdb, 3, 2)
        self._register_file = FPRegisterFile(32, self._cdb)
        self._adder = FloatingPointUnit("Add", self._cdb, 3, {"ADDD": 2, "SUBD": 2})
        self._multiplier = FloatingPointUnit(
            "Mult", self._cdb, 2, {"MULTD": 10, "DIVD": 20}
        )
        self._pc = 0
```

`CPU` 类的 `issue` 方法负责从寄存器中读取操作数（或产生该操作数的保留站）并调用对应功能单元的 `issue` 方法发射指令。如果发射成功，功能单元的 `issue` 方法返回对应的保留站编号，`CPU` 类的 `issue` 方法将该保留站编号写入目的寄存器的 `fu` 字段；如果功能单元的保留站已满，返回 `False`。

```python
def issue(self, instruction: str, pc: int) -> bool:
    op, dst, src1, src2 = instruction.split(" ")
    if op == "ADDD" or op == "SUBD":
        op1, op1_fu = self._register_file.read(int(src1[1:]))
        op2, op2_fu = self._register_file.read(int(src2[1:]))
        tag = self._adder.issue(pc, op, op1, op1_fu, op2, op2_fu)
    elif op == "MULTD" or op == "DIVD":
        op1, op1_fu = self._register_file.read(int(src1[1:]))
        op2, op2_fu = self._register_file.read(int(src2[1:]))
        tag = self._multiplier.issue(pc, op, op1, op1_fu, op2, op2_fu)
    elif op == "LD":
        tag = self._memory.issue_load(pc, src2, src1.replace("+", ""))
    elif op == "SD":
        data, data_fu = self._register_file.read(int(dst[1:]))
        tag = self._memory.issue_store( pc, src2, src1.replace("+", ""), data, data_fu)
    else:
        raise ValueError(f"Invalid operation: {op}")
    if tag and op != "SD":
        self._register_file.set_fu(int(dst[1:]), tag)
    return True if tag else False
```

`CPU` 类的 `run` 方法负责按顺序执行 `_instructions` 中的指令，直到所有指令都执行完毕。在每个时钟周期，它执行如下工作：

1. 调用 `issue` 方法发射指令，发射成功则程序计数器加 1，否则下个周期继续尝试发射该指令；
2. 调用各个功能单元的 `tick` 方法，执行一个时钟周期；
3. 调用寄存器组和 CDB 的 `tick` 方法，将结果写入寄存器和总线；
4. 打印本周期各个保留站和寄存器状态。

```python
def run(self):
    cycles = 1
    pre_out_str = ""
    same_counter = 0
    while (
        self._pc < len(self._instructions)
        or not self._adder.finished()
        or not self._multiplier.finished()
        or not self._memory.finished()
    ):
        # Issue
        if self._pc < len(self._instructions):
            if self.issue(self._instructions[self._pc], self._pc):
                self._issue_cycle[self._pc] = cycles
                self._pc += 1

        # Execute
        record = []
        record += self._adder.tick()
        record += self._multiplier.tick()
        record += self._memory.tick()
        for i in record:
            self._finish_cycle[i] = cycles

        # Write back
        self._register_file.tick()
        self._cdb.tick()

        # Print
        # 打印输出部分代码省略
```

### `FPRegisterFile` 类

`FPRegisterFile` 类位于 `units.py`，负责管理浮点寄存器。

```python
class FPRegisterFile:
    def __init__(self, n_registers: int, cbd: CommonDataBus):
        self._n_registers = n_registers
        self._cbd = cbd
        self.registers = [{"fu": "", "data": ""} for i in range(n_registers)]
```

`FPRegisterFile` 类的 `read` 方法负责从寄存器中读取数据。它首先检查要读取的数据是否在 CDB 上，是则返回 CDB 上的数据，否则继续检查对应寄存器中的数据是否已经写回，是则返回寄存器中的数据，否则返回对应的保留站编号。

```python
def read(self, register: int) -> tuple[str, str]:
    """Read a register
    Args:
        register: the register to read
    Returns:
        if the register is ready, return the data in the register and "",
        otherwise, return "" and the tag of the functional unit that is writing to the register
    """
    tag, data = self._cbd.read()
    if tag and tag == self.registers[register]["fu"]:
        return data, ""
    elif self.registers[register]["fu"] == "":
        return self.registers[register]["data"] if self.registers[register]["data"] else f"R(F{register})", ""
    else:
        return "", self.registers[register]["fu"]
```

`FPRegisterFile` 类的 `set_fu` 方法负责将保留站编号写入寄存器的 `fu` 字段，表示该寄存器的数据将由该保留站产生。

```python
def set_fu(self, register: int, fu: str):
    self.registers[register]["fu"] = fu
```

`FPRegisterFile` 类的 `tick` 方法负责将 CDB 上的数据写入寄存器。

```python
def tick(self):
    tag, data = self._cbd.read()
    if tag:
        for i in range(self._n_registers):
            if self.registers[i]["fu"] == tag:
                self.registers[i]["data"] = data
                self.registers[i]["fu"] = ""
```

### `FloatingPointUnit` 类

`FloatingPointUnit` 类位于 `units.py`，是浮点运算单元的抽象，可作为浮点加法器或浮点乘法器。属性 `_name` 指明当前对象是加法器还是乘法器，`_n_rs` 是保留站个数，`_n_cucles` 是执行各个浮点操作所需的周期数，`_rs_tail` 是保留站的尾指针。保留站中的字段 `counter` 表示该指令还需执行的周期数，为 `-1` 表示操作数还未就绪；`pc` 表示该指令的地址；保留站中的其他字段含义与课件一致，不再赘述。

```python
class FloatingPointUnit:
    def __init__(
        self, name: str, cdb: CommonDataBus, n_rs: int, n_cycles: dict[str, int]
    ):
        self._name = name
        self._cdb = cdb
        self._n_rs = n_rs
        self._n_cycles = n_cycles
        self.rs = [
            {"busy": False, "op": "", "Vj": "", "Vk": "", "Qj": "", "Qk": "", "counter": -1, "pc": 0}
        ] * n_rs
        self._rs_tail = 0
```

`FloatingPointUnit` 类的 `issue` 方法负责将指令发射到保留站中。属性 `_rs_tail` 是保留站的尾指针，如果 `rs[_rs_tail][busy] == True`，说明保留站已满，返回空串表示发射失败；否则把指令放到保留站 `rs[_rs_tail]` 中，并返回该保留站的编号。在发射指令时还需检查操作数是否就绪，如果操作数已就绪，`counter` 字段应置为 `self._n_cycles[op] + 1`，这是因为发射指令本身需要 1 个时钟周期。

```python
def issue(self, pc: int, op: str, op1: str, op1_fu:str, op2: str, op2_fu: str) -> str:
    """Issue an operation
    Args:
        pc: the program counter of the instruction
        op: the operation, can be "ADDD", "SUBD", "MULD" or "DIVD"
        op1: the first operand if it's ready, otherwise ""
        op1_fu: the functional unit that will produce the first operand
        op2: the second operand if it's ready, otherwise ""
        op2_fu: the functional unit that will produce the second operand
    Returns:
        The reservation station tag if the operation is successfully issued, otherwise ""
    """
    # Check if the reservation station is full
    if self.rs[self._rs_tail]["busy"]:
        return ""

    # Put the operation into the reservation station
    self.rs[self._rs_tail] = {
        "busy": True,
        "op": op,
        "Vj": op1,
        "Qj": op1_fu,
        "Vk": op2,
        "Qk": op2_fu,
        "counter": (self._n_cycles[op] + 1) if op1 and op2 else -1,
        "pc": pc,
    }
    tag = f"{self._name}{self._rs_tail+1}"
    self._rs_tail = (self._rs_tail + 1) % self._n_rs
    return tag
```

`FloatingPointUnit` 类的 `tick` 方法负责执行一个周期。它遍历每个保留站，如果该保留站的 `busy` 字段为 `True`，则通过 `counter` 判断指令处于哪个阶段并作相应操作；该函数会返回在该周期执行完毕的指令的 PC，方便后续打印输出。

```python
def tick(self) -> list[int]:
    record = [] # A list of instructions that are finished

    # Check CDB for required data
    tag, data = self._cdb.read()

    # Check each reservation station
    for i, rs in enumerate(self.rs):
        if rs["busy"]:
            if rs["counter"] == -1:    # Data is not ready
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
                record.append(rs['pc'])
                rs["counter"] -= 1
            elif rs["counter"] == 0:    # Write back finished
                rs["busy"] = False
                rs["op"], rs["Vj"], rs["Vk"], rs["Qj"], rs["Qk"] = "", "", "", "", ""
            else:    # Executing
                rs["counter"] -= 1

    return record
```

另外还有 `MemoryUnit` 类负责 Load 和 Store 指令，与 `FloatingPointUnit` 比较类似；还有 `CommonDataBus` 类，比较简单，均不再赘述。

## 实验结果与分析

完整输出结果见 `output1.txt` 和 `output2.txt`，这里只举例样例 1 中的前几条指令来说明本程序能够正确模拟 Tomasulo 动态调度算法。

```assembly
LD F6 34+ R2
LD F2 45+ R3
MULTD F0 F2 F4
SUBD F8 F6 F2
DIVD F10 F0 F6
ADDD F6 F8 F2
```

第 1 个时钟周期，发射第一条指令，程序输出如下：

```text
Cycle_1;
Load1:Yes,34+R2;
Load2:No,;
Load3:No,;
Store1:No,,;
Store2:No,,;
Store3:No,,;
Add1:No,,,,,;
Add2:No,,,,,;
Add3:No,,,,,;
Mult1:No,,,,,;
Mult2:No,,,,,;
F0:;F2:;F4:;F6:Load1;F8:;F10:;F12:;
```

第 2 个时钟周期，第一条指令开始执行，发射第二条指令，程序输出如下：

```text
Cycle_2;
Load1:Yes,34+R2;
Load2:Yes,45+R3;
Load3:No,;
Store1:No,,;
Store2:No,,;
Store3:No,,;
Add1:No,,,,,;
Add2:No,,,,,;
Add3:No,,,,,;
Mult1:No,,,,,;
Mult2:No,,,,,;
F0:;F2:Load2;F4:;F6:Load1;F8:;F10:;F12:;
```

第 3 个时钟周期，第二条指令开始执行，发射第三条指令（但是该指令所需的操作数 `F2` 依赖于第二条指令，尚未就绪），程序输出如下：

```text
Cycle_3;
Load1:Yes,34+R2;
Load2:Yes,45+R3;
Load3:No,;
Store1:No,,;
Store2:No,,;
Store3:No,,;
Add1:No,,,,,;
Add2:No,,,,,;
Add3:No,,,,,;
Mult1:Yes,MULTD,,R(F4),Load2,;
Mult2:No,,,,,;
F0:Mult1;F2:Load2;F4:;F6:Load1;F8:;F10:;F12:;
```

第 4 个时钟周期，第一条指令执行完毕，结果 `M(34+R2)` 写回寄存器 `F2`，发射第四条指令（但是该指令所需的操作数 `F2` 依赖于第二条指令，尚未就绪），程序输出如下：

```text
Cycle_4;
Load1:No,;
Load2:Yes,45+R3;
Load3:No,;
Store1:No,,;
Store2:No,,;
Store3:No,,;
Add1:Yes,SUBD,M(34+R2),,,Load2;
Add2:No,,,,,;
Add3:No,,,,,;
Mult1:Yes,MULTD,,R(F4),Load2,;
Mult2:No,,,,,;
F0:Mult1;F2:Load2;F4:;F6:M(34+R2);F8:Add1;F10:;F12:;
```

第 5 个时钟周期，第二条指令执行完毕，结果 `M(45+R3)` 写回寄存器 `F2`，同时第三、四条指令开始执行，发射第五条指令（但是该指令所需的操作数 `F0` 依赖于第三条指令，尚未就绪），程序输出如下：

```text
Cycle_5;
Load1:No,;
Load2:No,;
Load3:No,;
Store1:No,,;
Store2:No,,;
Store3:No,,;
Add1:Yes,SUBD,M(34+R2),M(45+R3),,;
Add2:No,,,,,;
Add3:No,,,,,;
Mult1:Yes,MULTD,M(45+R3),R(F4),,;
Mult2:Yes,DIVD,,M(34+R2),Mult1,;
F0:Mult1;F2:M(45+R3);F4:;F6:M(34+R2);F8:Add1;F10:Mult2;F12:;
```

第 6 个时钟周期，发射第六条指令（但是该指令所需的操作数 `F8` 依赖于第四条指令，尚未就绪）。第 7 个时钟周期，状态相同，合并输出：

```text
Cycle_6-7;
Load1:No,;
Load2:No,;
Load3:No,;
Store1:No,,;
Store2:No,,;
Store3:No,,;
Add1:Yes,SUBD,M(34+R2),M(45+R3),,;
Add2:Yes,ADDD,,M(45+R3),Add1,;
Add3:No,,,,,;
Mult1:Yes,MULTD,M(45+R3),R(F4),,;
Mult2:Yes,DIVD,,M(34+R2),Mult1,;
F0:Mult1;F2:M(45+R3);F4:;F6:Add2;F8:Add1;F10:Mult2;F12:;
```

这 6 条指令全部执行完共需 37 个时钟周期，不再一一赘述。最终每条指令发射、执行结束、写回的时钟周期如下：

```text
LD F6 34+ R2 :1,3,4;
LD F2 45+ R3 :2,4,5;
MULTD F0 F2 F4 :3,15,16;
SUBD F8 F6 F2 :4,7,8;
DIVD F10 F0 F6 :5,36,37;
ADDD F6 F8 F2 :6,10,11;
```
