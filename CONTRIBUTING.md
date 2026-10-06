# Contributing

Thanks for helping people practice data quality with reproducible examples.

1. Open an issue describing a concrete use case, expected behavior and a minimal synthetic example.
2. Create a branch, make a focused change and add a correctness test for new behavior.
3. Run `python -m unittest discover -s tests -v`.
4. Submit a pull request explaining the change and how it was validated.

Useful first contributions: Spanish examples, an independent detector, new profiles, CLI usability and new corruption operators with reversible answer-key events.

For new operators, define the error taxonomy, localization column and inverse operation. Verify byte reproducibility, clean-data validity and precision/recall cases. Do not use real personal or customer data in examples. Never feed `ground_truth.json` into a detector presented as independent.
