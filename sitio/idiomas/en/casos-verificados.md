# Verified cases

Nervi does not ask you to take its word for it: every type of calculation is compared with a known solution, and that comparison runs automatically on every change to the program. This page explains how verification works and lists the cases the library has today.

## How it is verified

- Each case is a text file with the model, the expected results and their **source**: a closed-form formula, a textbook with page and example number, or a solution worked by hand with exact arithmetic.
- The automatic check on GitHub solves every case on each contribution and turns red if any value drifts from the expected one by more than the tolerance (by default, a relative error of 1e-9).
- Besides these, the solver has dozens of analytical tests in Rust (mechanisms, space frame, dynamics, rigid offsets and diaphragms) and hundreds of tests in Python (file format, interface, calculation report and design).
- The **reinforced concrete design** modules (ACI 318-19) are verified with hand calculations and against open-source programs, but not yet against published examples or reviewed by a structural engineer, which is why they are marked experimental.

## Cases in the library

Today the [`verification/`](https://github.com/jeronimobareiro/nervi/tree/main/verification) folder has **{{N_CASOS}} cases**. Titles and sources are in Spanish, the project's working language:

{{CASOS}}

## How to contribute a case

Adding a case does not require knowing Rust or touching the solver: writing a text file is enough. A worked example from your course textbook is an excellent first contribution. The instructions are in the [library README](https://github.com/jeronimobareiro/nervi/blob/main/verification/README.md) and in [how to contribute](participar/index.md).
