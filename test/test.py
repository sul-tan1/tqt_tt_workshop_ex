# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.triggers import Timer

N = 4
MASK = (1 << N) - 1
SIGN = 1 << (N - 1)

ADD, SUB, AND, OR, XOR, CMP, LSL, LSR = range(8)


def model(a, b, op):
    """Return (result, carry, zero, neg, ov) as the ALU should produce them."""
    carry = 0
    ov = 0
    flag_val = 0

    if op in (ADD, SUB, CMP):
        b_eff = (~b & MASK) if op in (SUB, CMP) else b
        cin = 1 if op in (SUB, CMP) else 0
        full = a + b_eff + cin
        diff = full & MASK
        carry = (full >> N) & 1
        ov = int((a & SIGN) == (b_eff & SIGN) and (diff & SIGN) != (a & SIGN))
        result = 0 if op == CMP else diff
        flag_val = diff
    elif op == AND:
        result = a & b
        flag_val = result
    elif op == OR:
        result = a | b
        flag_val = result
    elif op == XOR:
        result = a ^ b
        flag_val = result
    elif op == LSL:
        result = (a << 1) & MASK
        carry = (a >> (N - 1)) & 1
        flag_val = result
    else:  # LSR
        result = a >> 1
        carry = a & 1
        flag_val = result

    zero = int(flag_val == 0)
    neg = (flag_val >> (N - 1)) & 1
    return result, carry, zero, neg, ov


@cocotb.test()
async def test_alu_exhaustive(dut):
    dut._log.info("Start")
    dut.ena.value = 1
    dut.rst_n.value = 1
    dut.clk.value = 0

    errors = 0
    for op in range(8):
        for a in range(16):
            for b in range(16):
                dut.ui_in.value = a | (b << 4)
                dut.uio_in.value = op
                # Allow the gate-level ripple-carry path to settle with UNIT_DELAY.
                await Timer(100, unit="ns")

                out = int(dut.uo_out.value)
                got = (
                    out & 0xF,
                    (out >> 4) & 1,
                    (out >> 5) & 1,
                    (out >> 6) & 1,
                    (out >> 7) & 1,
                )
                exp = model(a, b, op)
                assert int(dut.uio_oe.value) == 0, "All bidirectional pins must stay inputs"
                assert int(dut.uio_out.value) == 0, "Unused output drivers must stay low"
                if got != exp:
                    errors += 1
                    dut._log.error(
                        f"op={op} a={a:04b} b={b:04b}: got (res,C,Z,N,V)={got}, expected {exp}"
                    )

    assert errors == 0, f"{errors} mismatches"
