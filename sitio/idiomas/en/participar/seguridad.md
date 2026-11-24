# Critical errors and security

!!! info "Translation"
    This is a translation of the [Spanish original](../../../participar/seguridad/), which is the reference text.

Nervi calculates structures. An incorrect result can lead to an unsafe structure, so we treat these errors as a priority.

## What to report privately

- Incorrect results that could underestimate internal forces, deformations or the reinforcement required.
- Code checks that approve an element that does not comply.
- Software vulnerabilities (for example, when reading third-party files).

Write to **jerobareiro@gmail.com** with the smallest model that reproduces the problem, the Nervi version and the result you expected with its source. We reply as soon as possible and publish the fix together with a notice in the release notes.

Errors with no impact on safety (messages, documentation, performance) go as a public issue.

## Responsibility

Nervi is distributed **without any warranty**, under sections 15 and 16 of the [GPL-3.0 license](https://github.com/jeronimobareiro/nervi/blob/main/LICENSE). The software assists the professional; it does not replace their judgment. Every calculation used in a real project must be checked and signed by a licensed professional, who is responsible for the design.
